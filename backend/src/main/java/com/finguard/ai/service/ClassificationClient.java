package com.finguard.ai.service;

import com.finguard.ai.dto.ClassificationResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Map;

@Component
public class ClassificationClient {
    private final RestClient client;
    private final boolean enabled;
    private final PrivacyMasker masker;
    public ClassificationClient(@Value("${ai.enabled:false}") boolean enabled,
            @Value("${ai.server-url:http://localhost:8000}") String baseUrl,
            @Value("${ai.service-token:}") String serviceToken,
            @Value("${ai.timeout-ms:5000}") long timeoutMs, PrivacyMasker masker) {
        this.enabled = enabled; this.masker = masker;
        if (enabled && serviceToken.isBlank()) throw new IllegalArgumentException("ai.service-token is required when AI is enabled");
        if (timeoutMs < 1 || timeoutMs > 60000) throw new IllegalArgumentException("ai.timeout-ms must be 1..60000");
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(timeoutMs)).build());
        factory.setReadTimeout(Duration.ofMillis(timeoutMs));
        client = RestClient.builder().baseUrl(baseUrl).requestFactory(factory)
                .defaultHeader("X-Service-Token", serviceToken).build();
    }
    public ClassificationResult classify(String text) {
        if (!enabled) return ClassificationResult.unavailable(ClassificationResult.Status.NOT_REQUESTED, null);
        try {
            ClassificationResult result = client.post().uri("/internal/v1/classifications")
                    .body(Map.of("text", masker.mask(text))).retrieve().body(ClassificationResult.class);
            if (result == null || result.status() != ClassificationResult.Status.COMPLETED
                    || result.decision() == null || result.modelVersion() == null || result.modelVersion().isBlank()
                    || result.modelVersion().length() > 100 || result.errorCode() != null
                    || (result.decision() != ClassificationResult.Decision.ABSTAIN && result.label() == null)
                    || (result.decision() == ClassificationResult.Decision.FLAG && result.label() != ClassificationResult.Label.PHISHING)
                    || (result.decision() == ClassificationResult.Decision.PASS && result.label() != ClassificationResult.Label.NORMAL)) {
                return ClassificationResult.unavailable(ClassificationResult.Status.FAILED, "AI_INVALID_RESPONSE");
            }
            return result;
        } catch (org.springframework.web.client.RestClientResponseException e) {
            return ClassificationResult.unavailable(ClassificationResult.Status.FAILED, "AI_HTTP_ERROR");
        } catch (org.springframework.web.client.ResourceAccessException e) {
            return ClassificationResult.unavailable(ClassificationResult.Status.FAILED, "AI_UNAVAILABLE");
        } catch (org.springframework.web.client.RestClientException e) {
            return ClassificationResult.unavailable(ClassificationResult.Status.FAILED, "AI_INVALID_RESPONSE");
        }
    }
}
