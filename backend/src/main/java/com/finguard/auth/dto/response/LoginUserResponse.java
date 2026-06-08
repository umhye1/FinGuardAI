package com.finguard.auth.dto.response;

import com.finguard.user.domain.User;
import com.finguard.user.domain.UserRole;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class LoginUserResponse {

    private long userId;
    private String email;
    private String name;
    private UserRole role;

    public static LoginUserResponse from(User user) {
        return LoginUserResponse.builder()
                .userId(user.getUserId())
                .email(user.getEmail())
                .name(user.getName())
                .role(user.getRole())
                .build();
    }
}
