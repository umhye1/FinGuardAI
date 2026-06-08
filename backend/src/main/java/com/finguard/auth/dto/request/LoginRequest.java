package com.finguard.auth.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.validator.constraints.NotBlank;

@Getter
@NoArgsConstructor
public class LoginRequest {

    private String email;
    private String password;
}
