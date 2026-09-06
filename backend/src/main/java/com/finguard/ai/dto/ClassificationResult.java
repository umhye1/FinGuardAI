package com.finguard.ai.dto;

public record ClassificationResult(Status status, Label label, Decision decision, String modelVersion, String errorCode) {
    public enum Status { COMPLETED, NOT_REQUESTED, FAILED }
    public enum Label { PHISHING, NORMAL }
    public enum Decision { FLAG, PASS, ABSTAIN }
    public static ClassificationResult unavailable(Status status, String code) {
        return new ClassificationResult(status, null, Decision.ABSTAIN, null, code);
    }
}
