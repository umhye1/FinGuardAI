package com.finguard.ai.service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.*;

@Component
public class RagClient {
    public enum Status { ANSWERED, INSUFFICIENT_EVIDENCE, NOT_REQUESTED, FAILED }
    public record Result(Status status, String answer, List<Long> chunkIds, String modelVersion, String promptVersion, String reasonCode, String policyVersion, Map<String, CitationSnapshot> evidenceSnapshots) {
        public Result(Status status, String answer, List<Long> chunkIds, String modelVersion, String promptVersion) {
            this(status, answer, chunkIds, modelVersion, promptVersion, null, null, Map.of());
        }
    }
    public record CitationSnapshot(String contentHash, com.fasterxml.jackson.databind.JsonNode metadata) {}
    private final boolean enabled;
    private final RestClient client;
    private final PrivacyMasker masker;
    public RagClient(@Value("${ai.enabled:false}") boolean enabled,
            @Value("${ai.server-url:http://localhost:8000}") String url,
            @Value("${ai.service-token:}") String token,
            @Value("${ai.rag-timeout-ms:15000}") long timeoutMs, PrivacyMasker masker) {
        this.enabled = enabled; this.masker = masker;
        if (enabled && token.isBlank()) throw new IllegalArgumentException("ai.service-token is required when AI is enabled");
        if (timeoutMs < 1 || timeoutMs > 60000) throw new IllegalArgumentException("ai.rag-timeout-ms must be 1..60000");
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofMillis(timeoutMs)).build());
        factory.setReadTimeout(Duration.ofMillis(timeoutMs));
        client = RestClient.builder().baseUrl(url).requestFactory(factory).defaultHeader("X-Service-Token", token).build();
    }
    public Result answer(String question) {
        if (!enabled) return new Result(Status.NOT_REQUESTED, "문서 기반 AI 답변이 아직 연결되지 않았습니다.", List.of(), null, null);
        try {
            Result r = client.post().uri("/internal/v1/rag/answers").body(Map.of("question", masker.mask(question)))
                    .retrieve().body(Result.class);
            if (r == null || r.status() == null) return failure();
            if (r.status() == Status.INSUFFICIENT_EVIDENCE) return new Result(r.status(), holdMessage(r.reasonCode()), List.of(), null, null, safeReason(r.reasonCode()), "evidence-policy-v1".equals(r.policyVersion()) ? r.policyVersion() : null, Map.of());
            if (!"evidence-policy-v1".equals(r.policyVersion()) || r.evidenceSnapshots() == null
                    || !r.evidenceSnapshots().keySet().equals(r.chunkIds() == null ? Set.of() : new HashSet<>(r.chunkIds().stream().map(String::valueOf).toList()))
                    || r.status() != Status.ANSWERED || r.answer() == null || r.answer().isBlank() || r.answer().length() > 10000
                    || r.chunkIds() == null || r.chunkIds().isEmpty() || r.chunkIds().size() > 10
                    || r.chunkIds().stream().anyMatch(id -> id == null || id <= 0)
                    || r.modelVersion() == null || r.modelVersion().isBlank() || r.modelVersion().length() > 100
                    || r.promptVersion() == null || r.promptVersion().isBlank() || r.promptVersion().length() > 100) return failure();
            return new Result(r.status(), masker.mask(r.answer()), r.chunkIds().stream().distinct().toList(), r.modelVersion(), r.promptVersion(), r.reasonCode(), r.policyVersion(), r.evidenceSnapshots());
        } catch (org.springframework.web.client.RestClientException e) { return failure(); }
    }
    private static String safeReason(String reason) {
        return reason != null && Set.of("NEEDS_CLARIFICATION", "CONFLICTING_EVIDENCE", "CORPUS_CHANGED",
                "MISSING_REQUIRED_DOCUMENT", "MISSING_REQUIRED_CITATION", "UNREVIEWED_PROCEDURE",
                "MODEL_INSUFFICIENT_EVIDENCE", "CORPUS_LIMIT").contains(reason) ? reason : null;
    }
    private static String holdMessage(String reason) {
        if ("NEEDS_CLARIFICATION".equals(reason)) return "계좌 송금, 의심 문자·앱, 휴대폰 소액결제 중 어떤 상황인가요? 피해 상황을 함께 알려주세요.";
        if ("CONFLICTING_EVIDENCE".equals(reason)) return "공식 자료의 대응 절차가 서로 달라 답변을 보류합니다. 담당 기관의 확인이 필요합니다.";
        if ("CORPUS_CHANGED".equals(reason)) return "답변 도중 근거 자료가 변경되어 답변을 보류합니다. 다시 질문해주세요.";
        return "답변에 필요한 검토된 공식 문서 근거가 부족합니다.";
    }
    public static Result failure() { return new Result(Status.FAILED, "현재 근거를 확인한 AI 답변을 제공할 수 없습니다. 잠시 후 다시 시도해주세요.", List.of(), null, null); }
}
