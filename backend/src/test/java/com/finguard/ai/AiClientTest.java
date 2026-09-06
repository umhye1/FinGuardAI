package com.finguard.ai;

import com.finguard.ai.service.*;
import com.finguard.ai.dto.ClassificationResult;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.*;

class AiClientTest {
    HttpServer server;
    String url;
    AtomicReference<String> body = new AtomicReference<>();
    AtomicReference<String> token = new AtomicReference<>();
    AtomicReference<String> response = new AtomicReference<>();
    @BeforeEach void setup() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/v1/", exchange -> {
            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            token.set(exchange.getRequestHeaders().getFirst("X-Service-Token"));
            byte[] bytes = response.get().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, bytes.length);
            exchange.getResponseBody().write(bytes);
            exchange.close();
        });
        server.start(); url = "http://127.0.0.1:" + server.getAddress().getPort();
    }
    @AfterEach void cleanup() { server.stop(0); }
    ClassificationClient classifier() { return new ClassificationClient(true, url, "internal-test", 2000, new PrivacyMasker()); }
    @Test void masksExternalInputAndPreservesSeparateModelDecision() {
        response.set("{\"status\":\"COMPLETED\",\"label\":\"PHISHING\",\"decision\":\"FLAG\",\"modelVersion\":\"v1\"}");
        var result = classifier().classify("010-1234-5678 user@example.com 검찰청");
        assertThat(result.status()).isEqualTo(ClassificationResult.Status.COMPLETED);
        assertThat(body.get()).doesNotContain("010-1234-5678", "user@example.com").contains("[PHONE]", "[EMAIL]", "검찰청");
        assertThat(token.get()).isEqualTo("internal-test");
    }
    @Test void rejectsMalformedOrContradictoryOutputs() {
        response.set("{\"status\":\"COMPLETED\",\"label\":\"NORMAL\",\"decision\":\"FLAG\",\"modelVersion\":\"v1\"}");
        assertThat(classifier().classify("test").errorCode()).isEqualTo("AI_INVALID_RESPONSE");
        response.set("not-json");
        assertThat(classifier().classify("test").status()).isEqualTo(ClassificationResult.Status.FAILED);
    }
    @Test void disabledClientDoesNotCallAiAndConnectionFailureFallsBack() {
        assertThat(new ClassificationClient(false, url, "", 100, new PrivacyMasker()).classify("test").status())
                .isEqualTo(ClassificationResult.Status.NOT_REQUESTED);
        assertThat(body.get()).isNull();
        server.stop(0);
        assertThat(classifier().classify("test").errorCode()).isEqualTo("AI_UNAVAILABLE");
    }
    @Test void rejectsAnswerWithoutEvidence() {
        response.set("{\"status\":\"ANSWERED\",\"answer\":\"unsupported answer\",\"chunkIds\":[],\"modelVersion\":\"m1\",\"promptVersion\":\"p1\"}");
        assertThat(new RagClient(true, url, "test", 2000, new PrivacyMasker()).answer("question").status()).isEqualTo(RagClient.Status.FAILED);
    }
    @Test void insufficientEvidenceDoesNotExposeUntrustedAnswer() {
        response.set("{\"status\":\"INSUFFICIENT_EVIDENCE\",\"answer\":\"made up answer\"}");
        var result = new RagClient(true, url, "test", 2000, new PrivacyMasker()).answer("question");
        assertThat(result.status()).isEqualTo(RagClient.Status.INSUFFICIENT_EVIDENCE);
        assertThat(result.answer()).doesNotContain("made up");
    }
}
