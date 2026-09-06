package com.finguard.auth.service;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.List;

@Component
@RequiredArgsConstructor
public class TokenSessionStore {
    private final StringRedisTemplate redis;
    private static final DefaultRedisScript<Long> ROTATE = new DefaultRedisScript<>("""
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
            return 1
        end
        return 0
        """, Long.class);

    public void create(String sessionId, String refreshToken, long ttlMillis) {
        redis.opsForValue().set(key(sessionId), hash(refreshToken), Duration.ofMillis(Math.max(1, ttlMillis)));
    }
    public boolean rotate(String sessionId, String oldToken, String newToken, long ttlMillis) {
        return Long.valueOf(1).equals(redis.execute(ROTATE, List.of(key(sessionId)),
                hash(oldToken), hash(newToken), Long.toString(Math.max(1, ttlMillis))));
    }
    public boolean isActive(String sessionId) {
        return sessionId != null && Boolean.TRUE.equals(redis.hasKey(key(sessionId)));
    }
    public void revoke(String sessionId) { redis.delete(key(sessionId)); }
    private String key(String sessionId) { return "finguard:session:" + sessionId; }
    private String hash(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
}
