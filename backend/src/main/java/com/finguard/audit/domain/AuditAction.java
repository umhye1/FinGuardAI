package com.finguard.audit.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum AuditAction {


    UPLOAD_DOCUMENT("문서 업로드"),
    DELETE_DOCUMENT("문서 삭제"),

    CREATE_KEYWORD("키워드 등록"),
    UPDATE_KEYWORD("키워드 수정"),
    DEACTIVATE_KEYWORD("키워드 비활성화"),

    LOGIN("로그인"),
    LOGOUT("로그아웃");

    private final String label;
}
