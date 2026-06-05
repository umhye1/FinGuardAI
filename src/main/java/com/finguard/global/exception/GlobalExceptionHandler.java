package com.finguard.global.exception;

import com.finguard.global.response.CommonResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(LoginFailedException.class)
    public ResponseEntity<CommonResponse<Void>> handleLoginFailedException(LoginFailedException e) {
        return ResponseEntity
                .status(HttpStatus.UNAUTHORIZED)
                .body(CommonResponse.fail(401,e.getMessage()));
    }


    @ExceptionHandler(DuplicateEmailException.class)
    public ResponseEntity<CommonResponse<Void>> handleDuplicateEmailException(DuplicateEmailException e) {
        return ResponseEntity
                .status(HttpStatus.CONFLICT)
                .body(CommonResponse.fail(409, e.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<CommonResponse<Void>> handleIllegalArgumentException(IllegalArgumentException e) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(CommonResponse.fail(400, e.getMessage()));
    }
}
