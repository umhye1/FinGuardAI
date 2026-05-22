package com.finguard.auth.dto;

import lombok.Builder;
import lombok.Getter;
import com.finguard.user.domain.UserRole;
import com.finguard.user.domain.User;

import java.time.LocalDateTime;

@Getter
@Builder
public class SignupResponse {
    private Long userId;
    private String email;
    private String name;
    private UserRole role;
    private LocalDateTime createdAt;

    public static SignupResponse from(User user) {
        return SignupResponse.builder()
                .userId(user.getUserId())
                .email(user.getEmail())
                .name(user.getName())
                .role(user.getRole())
                .createdAt(user.getCreatedAt())
                .build();
    }
}
