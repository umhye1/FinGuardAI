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
    public record Result(Status status, String answer, List<Long> chunkIds, String modelVersion, String promptVersion) {}
    private final boolean enabled;
    private final RestClient client;
    private final PrivacyMasker masker;
    public RagClient(@Value("${ai.enabled:false}") boolean enabled,
            @Value("${ai.server-url:http://localhost:8000}") String url,
            @Value("${ai.service-token:}") String token,
            @Value("${ai.timeout-ms:5000}") long timeoutMs, PrivacyMasker masker) {
        this.enabled = enabled; this.masker = masker;
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
            if (r.status() == Status.INSUFFICIENT_EVIDENCE) return new Result(r.status(), "답변에 필요한 공식 문서 근거가 부족합니다.", List.of(), null, null);
            if (r.status() != Status.ANSWERED || r.answer() == null || r.answer().isBlank() || r.answer().length() > 10000
                    || r.chunkIds() == null || r.chunkIds().isEmpty() || r.chunkIds().size() > 10
                    || r.chunkIds().stream().anyMatch(id -> id == null || id <= 0)
                    || r.modelVersion() == null || r.modelVersion().isBlank() || r.modelVersion().length() > 100
                    || r.promptVersion() == null || r.promptVersion().isBlank() || r.promptVersion().length() > 100) return failure();
            return new Result(r.status(), masker.mask(r.answer()), r.chunkIds().stream().distinct().toList(), r.modelVersion(), r.promptVersion());
        } catch (org.springframework.web.client.RestClientException e) { return failure(); }
    }
    public static Result failure() { return new Result(Status.FAILED, "현재 근거를 확인한 AI 답변을 제공할 수 없습니다. 잠시 후 다시 시도해주세요.", List.of(), null, null); }
}
