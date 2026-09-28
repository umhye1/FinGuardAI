package com.finguard.analysis.service;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class KeywordMatcherTest {
    @Test void handlesSpacingUnicodeAndCase() {
        assertTrue(KeywordMatcher.matches("저금리 대출 승인", "저금리대출"));
        assertTrue(KeywordMatcher.matches("원격\u200b제어 앱", "원격제어"));
        assertTrue(KeywordMatcher.matches("ＡＰＫ 설치", "apk"));
        assertFalse(KeywordMatcher.matches("내일 카페에서 만나요", "계좌이체"));
        assertFalse(KeywordMatcher.matches("내용", "  "));
    }
    @Test void preventionTextRemainsLexicalEvidenceNotAnAutomaticSafeBypass() {
        assertTrue(KeywordMatcher.matches("검찰청 사칭 문자를 클릭하지 마세요", "검찰청"));
    }
}
