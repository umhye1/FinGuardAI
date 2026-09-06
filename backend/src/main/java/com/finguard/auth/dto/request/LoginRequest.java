package com.finguard.auth.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;
import jakarta.validation.constraints.NotBlank;

@Getter
@NoArgsConstructor
public class LoginRequest {

    @jakarta.validation.constraints.NotBlank
    @Email
    private String email;
    @jakarta.validation.constraints.NotBlank
    @Size(max = 72)
    private String password;
}
