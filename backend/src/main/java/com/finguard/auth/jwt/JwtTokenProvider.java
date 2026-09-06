package com.finguard.auth.jwt;

import com.finguard.user.domain.UserRole;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class JwtTokenProvider {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.access-token-expiration}")
    private long accessTokenExpiration;

    @Value("${jwt.refresh-token-expiration}")
    private long refreshTokenExpiration;

    private SecretKey secretKey;

    @PostConstruct
    public void init(){
        this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    public String createAccessToken(Long userId, String email, UserRole role, String sessionId) {
        Date now  = new Date();
        Date expiration = new Date(now.getTime() + accessTokenExpiration);

        return Jwts.builder()
                .subject(email)
                .claim("userId", userId)
                .claim("role",role.name())
                .claim("type", "access")
                .claim("sid", sessionId)
                .id(UUID.randomUUID().toString())
                .issuedAt(now)
                .expiration(expiration)
                .signWith(secretKey)
                .compact();
    }

    public String createRefreshToken(Long userId, String email, String sessionId) {
        Date now  = new Date();
        Date expiration = new Date(now.getTime() + refreshTokenExpiration);

        return Jwts.builder()
                .subject(email)
                .claim("userId", userId)
                .claim("type", "refresh")
                .claim("sid", sessionId)
                .id(UUID.randomUUID().toString())
                .issuedAt(now)
                .expiration(expiration)
                .signWith(secretKey)
                .compact();
    }

    public String getEmail(String token){
        return getClaims(token).getSubject();
    }

    public Long getUserId(String token){
        Number userId = getClaims(token).get("userId", Number.class);
        return userId.longValue();
    }

    public String getRole(String token){
        return getClaims(token).get("role",String.class);
    }

    public boolean validateToken(String token){
        try{
            getClaims(token);
            return true;
        }catch (Exception e){
            return false;
        }
    }

    public String getSessionId(String token) {
        return getClaims(token).get("sid", String.class);
    }

    public boolean validateAccessToken(String token) { return validateType(token, "access"); }
    public boolean validateRefreshToken(String token) { return validateType(token, "refresh"); }

    private boolean validateType(String token, String type) {
        try {
            Claims claims = getClaims(token);
            return type.equals(claims.get("type", String.class))
                    && claims.getSubject() != null && !claims.getSubject().isBlank()
                    && claims.get("userId", Number.class) != null
                    && claims.get("sid", String.class) != null
                    && claims.getId() != null;
        } catch (Exception e) { return false; }
    }

    public long getRemainingExpiration(String token){
        Date expiration = getClaims(token).getExpiration();
        return expiration.getTime() - System.currentTimeMillis();
    }

    private Claims getClaims(String token){
        return Jwts.parser()
                .verifyWith(secretKey)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

}
