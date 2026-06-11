package com.finguard.global.exception;

import com.finguard.global.response.CommonResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

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

    @ExceptionHandler(UnauthorizedException.class)
    public ResponseEntity<CommonResponse<Void>> handleUnauthorizedException(UnauthorizedException e) {
        return ResponseEntity
                .status(HttpStatus.UNAUTHORIZED)
                .body(CommonResponse.fail(401, e.getMessage()));
    }

    @ExceptionHandler(BadRequestException.class)
    public ResponseEntity<CommonResponse<Void>> handleBadRequestException(BadRequestException e) {
        return ResponseEntity.badRequest()
                .body(CommonResponse.fail(400, e.getMessage()));
    }

    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<CommonResponse<Void>> handleNotFoundException(NotFoundException e) {
        return ResponseEntity.status(404)
                .body(CommonResponse.fail(404, e.getMessage()));
    }

    @ExceptionHandler(ConflictException.class)
    public ResponseEntity<CommonResponse<Void>> handleConflictException(ConflictException e) {
        return ResponseEntity.status(409)
                .body(CommonResponse.fail(409, e.getMessage()));
    }

    @ExceptionHandler(ForbiddenException.class)
    public ResponseEntity<CommonResponse<Void>> handleForbiddenException(ForbiddenException e) {
        return ResponseEntity.status(403)
                .body(CommonResponse.fail(403, e.getMessage()));
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<CommonResponse<Void>> handleMaxUploadSizeExceededException(
            MaxUploadSizeExceededException e
    ) {
        return ResponseEntity.status(413)
                .body(CommonResponse.fail(413, "업로드 가능한 파일 크기를 초과했습니다."));
    }
}
