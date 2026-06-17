package com.finguard.audit.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum AuditTargetType {

    DOCUMENT("문서"),
    KEYWORD("위험 키워드"),
    USER("사용자"),
    AUTH("인증"),
    ANALYSIS("분석");

    private final String label;
}
