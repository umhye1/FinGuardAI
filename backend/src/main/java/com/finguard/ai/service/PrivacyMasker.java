package com.finguard.ai.service;
import org.springframework.stereotype.Component;

/** Baseline redaction, not a complete PII detector. No request/response bodies are logged. */
@Component
public class PrivacyMasker {
    public String mask(String text) {
        return text
            .replaceAll("(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", "[EMAIL]")
            .replaceAll("(?<!\\d)\\d{6}[- ]?[1-4]\\d{6}(?!\\d)", "[ID_NUMBER]")
            .replaceAll("(?<!\\d)(?:\\+82[- ]?|0)1[016789][- ]?\\d{3,4}[- ]?\\d{4}(?!\\d)", "[PHONE]")
            .replaceAll("(?<!\\d)\\d{2,6}[- ]\\d{2,6}[- ]\\d{2,8}(?!\\d)", "[NUMBER]");
    }
}
