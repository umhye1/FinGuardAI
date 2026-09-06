package com.finguard;

import com.finguard.auth.jwt.JwtTokenProvider;
import com.finguard.auth.service.TokenSessionStore;
import com.finguard.document.dto.request.DocumentCreateRequest;
import com.finguard.document.repository.*;
import com.finguard.document.service.DocumentService;
import com.finguard.job.service.*;
import com.finguard.job.repository.ProcessingJobRepository;
import com.finguard.job.domain.ProcessingJob;
import com.finguard.user.domain.*;
import com.finguard.user.repository.UserRepository;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.*;
import org.testcontainers.utility.DockerImageName;
import java.nio.file.*;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Testcontainers
@SpringBootTest(properties = {"spring.config.location=classpath:application-test.properties", "jobs.worker.enabled=false"})
@AutoConfigureMockMvc
class FinguardApiApplicationTests {
    @Container static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));
    @Container static GenericContainer<?> redis = new GenericContainer<>(DockerImageName.parse("redis:7-alpine")).withExposedPorts(6379);
    static Path uploads;
    static { try { uploads = Files.createTempDirectory("finguard-test-uploads-"); } catch(Exception e) { throw new RuntimeException(e); } }
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", postgres::getJdbcUrl);
        r.add("spring.datasource.username", postgres::getUsername);
        r.add("spring.datasource.password", postgres::getPassword);
        r.add("spring.data.redis.host", redis::getHost);
        r.add("spring.data.redis.port", () -> redis.getMappedPort(6379));
        r.add("file.upload-dir", uploads::toString);
    }
    @Autowired JdbcTemplate jdbc;
    @Autowired DocumentService documents;
    @Autowired DocumentRepository documentRepository;
    @Autowired DocumentChunkRepository chunks;
    @Autowired DocumentJobService jobs;
    @Autowired ProcessingJobRepository jobRepository;
    @Autowired UserRepository users;
    @Autowired TokenSessionStore sessions;
    @Autowired JwtTokenProvider tokens;
    @Autowired com.finguard.analysis.service.AnalysisService analyses;
    @Autowired com.finguard.review.service.ReviewService reviews;
    @Autowired com.finguard.chat.service.ChatAnswerWriter chatWriter;
    @Autowired com.finguard.chat.repository.ChatSessionRepository chatSessions;
    @Autowired MockMvc mvc;
    User admin;
    @BeforeEach void setup() {
        jdbc.execute("TRUNCATE users CASCADE");
        admin = users.save(User.builder().email("admin@test.dev").name("Admin").password("unused").role(UserRole.ADMIN).build());
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(admin.getEmail(), null, List.of()));
    }
    @AfterEach void cleanup() { org.springframework.security.test.context.TestSecurityContextHolder.clearContext(); }
    @AfterAll static void removeFiles() throws Exception {
        try (var paths = Files.walk(uploads)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path);
        }
    }
    DocumentCreateRequest request() throws Exception {
        return new com.fasterxml.jackson.databind.ObjectMapper().readValue("{\"title\":\"Guide\",\"source\":\"Official\"}", DocumentCreateRequest.class);
    }
    @Test void migrationAndDocumentRetryAreDurableAndDoNotDuplicateChunks() throws Exception {
        var upload = documents.createDocument(new MockMultipartFile("file", "guide.txt", "text/plain", "official guide".getBytes()), request(), "127.0.0.1");
        var work = jobs.claim().orElseThrow();
        assertThatThrownBy(() -> jobs.complete(work, " ")).isInstanceOf(IllegalArgumentException.class);
        jobs.fail(work, "EMPTY_TEXT");
        assertThat(jobRepository.findById(upload.getJobId()).orElseThrow().getStatus()).isEqualTo(ProcessingJob.Status.FAILED);
        assertThat(documentRepository.findById(upload.getDocumentId()).orElseThrow().getStatus().name()).isEqualTo("FAILED");
        documents.retry(upload.getDocumentId());
        var retry = jobs.claim().orElseThrow();
        jobs.complete(retry, "official guide");
        jobs.complete(retry, "duplicate result");
        assertThat(chunks.count()).isEqualTo(1);
        assertThat(documentRepository.findById(upload.getDocumentId()).orElseThrow().getChunkCount()).isEqualTo(1);
        documents.retry(upload.getDocumentId());
        jobs.complete(jobs.claim().orElseThrow(), "replacement guide");
        assertThat(chunks.count()).isEqualTo(1);
    }
    @Test void duplicateProcessingAndDeleteWhilePendingAreRejected() throws Exception {
        var doc = documents.createDocument(new MockMultipartFile("file", "guide.txt", "text/plain", "guide".getBytes()), request(), "ip");
        assertThatThrownBy(() -> documents.retry(doc.getDocumentId())).isInstanceOf(com.finguard.global.exception.ConflictException.class);
        assertThatThrownBy(() -> documents.deleteDocument(doc.getDocumentId(), "ip")).isInstanceOf(com.finguard.global.exception.ConflictException.class);
    }
    @Test void oldWorkerCannotPublishAfterLeaseIsReclaimed() throws Exception {
        var doc = documents.createDocument(new MockMultipartFile("file", "guide.txt", "text/plain", "guide".getBytes()), request(), "ip");
        var old = jobs.claim().orElseThrow();
        jdbc.update("UPDATE processing_jobs SET lease_until = now() - interval '1 minute' WHERE job_id = ?", doc.getJobId());
        var current = jobs.claim().orElseThrow();
        jobs.complete(old, "stale");
        assertThat(chunks.count()).isZero();
        jobs.complete(current, "current");
        assertThat(chunks.findAll().getFirst().getContent()).isEqualTo("current");
    }
    @Test void rejectsUnsupportedFilesBeforeSaving() throws Exception {
        assertThatThrownBy(() -> documents.createDocument(new MockMultipartFile("file", "noextension", "text/plain", "guide".getBytes()), request(), "ip"))
                .isInstanceOf(com.finguard.global.exception.BadRequestException.class);
        assertThat(documentRepository.count()).isZero();
    }
    @Test void redisRotationIsAtomicAndLogoutRevokesApiAccess() throws Exception {
        String sid = UUID.randomUUID().toString();
        String access = tokens.createAccessToken(admin.getUserId(), admin.getEmail(), admin.getRole(), sid);
        String refresh = tokens.createRefreshToken(admin.getUserId(), admin.getEmail(), sid);
        sessions.create(sid, refresh, 120000);
        org.springframework.security.test.context.TestSecurityContextHolder.clearContext();
        mvc.perform(get("/api/admin/dashboard").header("Authorization", "Bearer " + refresh)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/admin/dashboard").header("Authorization", "Bearer " + access)).andExpect(status().isOk());
        assertThat(sessions.rotate(sid, refresh, "replacement", 120000)).isTrue();
        assertThat(sessions.rotate(sid, refresh, "reused", 120000)).isFalse();
        mvc.perform(post("/api/auth/logout").header("Authorization", "Bearer " + access)
                .contentType("application/json").content("{\"refreshToken\":\"" + refresh + "\"}"))
                .andExpect(status().isOk());
        mvc.perform(get("/api/auth/me").header("Authorization", "Bearer " + access)).andExpect(status().isUnauthorized());
    }
    @Test void analysisPersistsWithoutAiAndFeedbackRequiresOwnership() throws Exception {
        var request = new com.fasterxml.jackson.databind.ObjectMapper().readValue("{\"text\":\"hello\"}", com.finguard.analysis.dto.request.AnalysisRequest.class);
        var analysis = analyses.analyze(request);
        assertThat(analysis.getModelResult().status()).isEqualTo(com.finguard.ai.dto.ClassificationResult.Status.NOT_REQUESTED);
        assertThat(analyses.getDetail(analysis.getAnalysisId()).getModelResult().status()).isEqualTo(analysis.getModelResult().status());
        var feedback = reviews.submit(admin.getEmail(), analysis.getAnalysisId(), com.finguard.review.domain.AnalysisReview.FeedbackType.OTHER, "검토 요청");
        var reviewed = reviews.review(admin.getEmail(), feedback.getReviewId(), feedback.getVersion(),
                com.finguard.review.domain.AnalysisReview.Label.NORMAL, "정상 메시지");
        assertThat(reviewed.getStatus()).isEqualTo(com.finguard.review.domain.AnalysisReview.Status.REVIEWED);
        assertThatThrownBy(() -> reviews.review(admin.getEmail(), feedback.getReviewId(), feedback.getVersion(),
                com.finguard.review.domain.AnalysisReview.Label.PHISHING, "stale"))
                .isInstanceOf(com.finguard.global.exception.ConflictException.class);
        var other = users.save(User.builder().email("other@test.dev").name("Other").password("unused").role(UserRole.USER).build());
        assertThatThrownBy(() -> reviews.submit(other.getEmail(), analysis.getAnalysisId(), com.finguard.review.domain.AnalysisReview.FeedbackType.OTHER, null))
                .isInstanceOf(com.finguard.global.exception.NotFoundException.class);
    }
    @Test void fabricatedRagCitationIsRejectedAndKnownCitationIsSnapshotted() throws Exception {
        var session = chatSessions.save(com.finguard.chat.domain.ChatSession.builder().user(admin).title("test").build());
        var fabricated = new com.finguard.ai.service.RagClient.Result(com.finguard.ai.service.RagClient.Status.ANSWERED,
                "untrusted", List.of(999999L), "model1", "prompt1");
        var rejected = chatWriter.save(admin.getEmail(), session.getSessionId(), "question", fabricated);
        assertThat(rejected.getAiMessage().getGenerationStatus()).isEqualTo("FAILED");
        assertThat(rejected.getAiMessage().getReferencedChunks()).isEmpty();
        documents.createDocument(new MockMultipartFile("file", "guide.txt", "text/plain", "guide".getBytes()), request(), "ip");
        jobs.complete(jobs.claim().orElseThrow(), "official guide");
        Long chunkId = chunks.findAll().getFirst().getChunkId();
        var accepted = chatWriter.save(admin.getEmail(), session.getSessionId(), "question",
                new com.finguard.ai.service.RagClient.Result(com.finguard.ai.service.RagClient.Status.ANSWERED,
                        "answer", List.of(chunkId), "model1", "prompt1"));
        assertThat(accepted.getAiMessage().getReferencedChunks()).hasSize(1);
        assertThat(accepted.getAiMessage().getReferencedChunks().getFirst().getContentPreview()).isEqualTo("official guide");
    }
    @Test void concurrentRefreshHasExactlyOneWinner() {
        String sid = UUID.randomUUID().toString();
        sessions.create(sid, "old-token", 60000);
        var futures = java.util.stream.IntStream.range(0, 10).mapToObj(i ->
                java.util.concurrent.CompletableFuture.supplyAsync(() -> sessions.rotate(sid, "old-token", "new-" + i, 60000))).toList();
        long winners = futures.stream().map(java.util.concurrent.CompletableFuture::join).filter(Boolean::booleanValue).count();
        assertThat(winners).isEqualTo(1);
        sessions.revoke(sid);
    }
}
