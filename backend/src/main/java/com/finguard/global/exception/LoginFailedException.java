package com.finguard.global.exception;

public class LoginFailedException extends RuntimeException{
    public LoginFailedException(String message) {
        super(message);
    }
}
