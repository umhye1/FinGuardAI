package com.finguard.chat.service;
import com.finguard.ai.service.RagClient;
import com.finguard.chat.domain.*;
import com.finguard.chat.dto.response.*;
import com.finguard.chat.repository.*;
import com.finguard.document.domain.DocumentStatus;
import com.finguard.document.repository.DocumentChunkRepository;
import com.finguard.global.exception.NotFoundException;
import com.finguard.user.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Service
@RequiredArgsConstructor
public class ChatAnswerWriter {
    private final ChatSessionRepository sessions;
    private final ChatMessageRepository messages;
    private final DocumentChunkRepository chunks;
    private final UserRepository users;
    private final ObjectMapper mapper;
    private boolean validEvidence(com.finguard.document.domain.DocumentChunk chunk, RagClient.Result result) {
        try {
            if (!"evidence-policy-v1".equals(result.policyVersion()) || result.evidenceSnapshots() == null) return false;
            var snapshot = result.evidenceSnapshots().get(String.valueOf(chunk.getChunkId()));
            if (snapshot == null || chunk.getDocument().getEvidenceMetadata() == null) return false;
            var metadata = mapper.readTree(chunk.getDocument().getEvidenceMetadata());
            String hash = java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                    .digest(chunk.getContent().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            return metadata.equals(snapshot.metadata()) && hash.equals(snapshot.contentHash())
                    && hash.equals(metadata.path("content_sha256").asText())
                    && "OFFICIAL_GUIDANCE".equals(metadata.path("kind").asText())
                    && Objects.equals(chunk.getDocument().getSourceUrl(), metadata.path("source_url").asText())
                    && !java.time.LocalDate.parse(metadata.path("review_due").asText()).isBefore(java.time.LocalDate.now());
        } catch (Exception e) { return false; }
    }
    @Transactional
    public ChatAnswerResponse save(String email, Long sessionId, String question, RagClient.Result result) {
        var user = users.findByEmail(email).orElseThrow();
        var session = sessions.findBySessionIdAndUserAndDeletedFalse(sessionId, user)
                .orElseThrow(() -> new NotFoundException("채팅 세션을 찾을 수 없습니다."));
        List<ReferencedChunkResponse> references = new ArrayList<>();
        if (result.status() == RagClient.Status.ANSWERED) {
            final var resultSnapshot = result;
            var found = chunks.findAllById(result.chunkIds());
            if (found.size() != result.chunkIds().size() || found.stream().anyMatch(c -> c.getDocument().getStatus() != DocumentStatus.COMPLETED || !validEvidence(c, resultSnapshot))) {
                result = RagClient.failure();
            } else {
                for (var chunk : found) references.add(ReferencedChunkResponse.builder()
                        .chunkId(chunk.getChunkId()).documentId(chunk.getDocument().getDocumentId())
                        .documentTitle(chunk.getDocument().getTitle()).contentPreview(chunk.getContent())
                        .sourceUrl(chunk.getDocument().getSourceUrl()).evidenceMetadata(chunk.getDocument().getEvidenceMetadata()).build());
            }
        }
        String json;
        try { json = mapper.writeValueAsString(references); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new IllegalStateException(e); }
        var userMessage = messages.save(ChatMessage.builder().session(session).sender(MessageSender.USER).message(question).build());
        var aiMessage = ChatMessage.builder().session(session).sender(MessageSender.AI).message(result.answer()).referencedChunks(json).build();
        aiMessage.setEvidenceDecision(result.reasonCode(), result.policyVersion());
        aiMessage.setGenerationMetadata(result.status().name(), result.modelVersion(), result.promptVersion());
        messages.saveAndFlush(aiMessage);
        session.touch();
        return ChatAnswerResponse.of(userMessage, aiMessage);
    }
}
