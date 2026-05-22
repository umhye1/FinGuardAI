package com.finguard.global.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class CommonResponse<T> {
    private int statusCode;
    private String message;
    private T data;

    public static <T> CommonResponse<T> success(int statusCode, String message, T data) {
        return new CommonResponse<>(statusCode, message,data);
    }

    public static <T> CommonResponse<T> success(String message,T data) {
        return new CommonResponse<>(200, message, data);
    }

    public static <T> CommonResponse<Void> success(String message) {
        return new CommonResponse<>(200,message, null);
    }

    public static <T> CommonResponse<Void>fail(int statusCode, String message) {
        return new CommonResponse<>(statusCode,message,null);
    }
}
