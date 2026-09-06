package com.finguard.auth.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class LogoutRequest {
    @jakarta.validation.constraints.NotBlank
    private String refreshToken;
}
