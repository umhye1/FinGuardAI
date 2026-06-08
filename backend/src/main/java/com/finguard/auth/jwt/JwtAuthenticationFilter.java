package com.finguard.auth.jwt;

import com.finguard.user.domain.User;
import com.finguard.user.repository.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    private final JwtTokenProvider jwtTokenProvider;
    private final UserRepository userRepository;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    )throws ServletException, IOException {

        String authorizationHeader = request.getHeader("Authorization");
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        String accessToken = authorizationHeader.substring(7);

        if(!jwtTokenProvider.validateToken(accessToken)) {
            filterChain.doFilter(request, response);
            return;
        }

        String email = jwtTokenProvider.getEmail(accessToken);
        User user = userRepository.findByEmail(email)
                .orElse(null);

        if (user == null) {
            filterChain.doFilter(request, response);
            return;
        }

        System.out.println("요청 URI = " + request.getRequestURI());
        System.out.println("email = " + email);
        System.out.println("role = " + user.getRole());


        SimpleGrantedAuthority authority =
                new SimpleGrantedAuthority("ROLE_" + user.getRole().name());

        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                user.getEmail(),
                null,
                List.of(authority)
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);

        System.out.println("authentication = " + SecurityContextHolder.getContext().getAuthentication());
        System.out.println("isAuthenticated = " + SecurityContextHolder.getContext().getAuthentication().isAuthenticated());

        filterChain.doFilter(request, response);
    }

}
