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
    @Transactional
    public ChatAnswerResponse save(String email, Long sessionId, String question, RagClient.Result result) {
        var user = users.findByEmail(email).orElseThrow();
        var session = sessions.findBySessionIdAndUserAndDeletedFalse(sessionId, user)
                .orElseThrow(() -> new NotFoundException("채팅 세션을 찾을 수 없습니다."));
        List<ReferencedChunkResponse> references = new ArrayList<>();
        if (result.status() == RagClient.Status.ANSWERED) {
            var found = chunks.findAllById(result.chunkIds());
            if (found.size() != result.chunkIds().size() || found.stream().anyMatch(c -> c.getDocument().getStatus() != DocumentStatus.COMPLETED)) {
                result = RagClient.failure();
            } else {
                for (var chunk : found) references.add(ReferencedChunkResponse.builder()
                        .chunkId(chunk.getChunkId()).documentId(chunk.getDocument().getDocumentId())
                        .documentTitle(chunk.getDocument().getTitle()).contentPreview(chunk.getContent()).build());
            }
        }
        String json;
        try { json = mapper.writeValueAsString(references); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new IllegalStateException(e); }
        var userMessage = messages.save(ChatMessage.builder().session(session).sender(MessageSender.USER).message(question).build());
        var aiMessage = ChatMessage.builder().session(session).sender(MessageSender.AI).message(result.answer()).referencedChunks(json).build();
        aiMessage.setGenerationMetadata(result.status().name(), result.modelVersion(), result.promptVersion());
        messages.saveAndFlush(aiMessage);
        session.touch();
        return ChatAnswerResponse.of(userMessage, aiMessage);
    }
}
