package com.finguard.analysis.service;

import java.text.Normalizer;
import java.util.Locale;

/** Lexical evidence only: matching a term does not establish malicious intent. */
public final class KeywordMatcher {
    private KeywordMatcher() {}
    public static String normalize(String value) {
        return Normalizer.normalize(value, Normalizer.Form.NFKC)
                .replaceAll("[\\p{Z}\\s\\p{Cf}]+", "").toLowerCase(Locale.ROOT);
    }
    public static boolean matches(String text, String keyword) {
        String normalized = normalize(keyword);
        return !normalized.isEmpty() && normalize(text).contains(normalized);
    }
}
