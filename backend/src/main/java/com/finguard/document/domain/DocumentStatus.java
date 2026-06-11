package com.finguard.document.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum DocumentStatus {
    UPLOADED("업로드 완료"),
    PROCESSING("처리 중"),
    COMPLETED("처리 완료"),
    FAILED("처리 실패");

    private final String label;
}
