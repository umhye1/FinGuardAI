package com.finguard.auth.dto.response;

import com.finguard.user.domain.User;
import lombok.Builder;
import lombok.Getter;


@Getter
@Builder
public class LoginResponse {
    private String accessToken;
    private String refreshToken;

    private LoginUserResponse user;

    public static LoginResponse of(User user,String accessToken, String refreshToken) {
        return LoginResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .user(LoginUserResponse.from(user))
                .build();
    }
}
