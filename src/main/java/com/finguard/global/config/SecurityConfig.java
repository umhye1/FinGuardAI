package com.finguard.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf->csrf.disable())
                .formLogin(form->form.disable())
                .httpBasic(httpBasic->httpBasic.disable())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
//                                로그인 없이 접근 가능하게 함, 나머지는 인증 필요하게 둠
                                "/actuator/health",
                                "/api/auth/signup",
                                "/api/auth/login"
                        ).permitAll()
                        .anyRequest().authenticated()
                );
        return http.build();
    }
}
