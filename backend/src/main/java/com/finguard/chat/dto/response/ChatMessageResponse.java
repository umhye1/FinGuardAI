package com.finguard.chat.dto.response;

import com.finguard.chat.domain.ChatMessage;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class ChatMessageResponse {
    private String generationStatus;
    private String modelVersion;
    private String promptVersion;
    private Long messageId;
    private String sender;
    private String message;
    private List<ReferencedChunkResponse> referencedChunks;
    private LocalDateTime createdAt;

    public static ChatMessageResponse from(ChatMessage message) {
        return ChatMessageResponse.builder()
                .messageId(message.getMessageId())
                .sender(message.getSender().name())
                .message(message.getMessage())
                .referencedChunks(parseReferences(message.getReferencedChunks()))
                .generationStatus(message.getGenerationStatus())
                .modelVersion(message.getModelVersion())
                .promptVersion(message.getPromptVersion())
                .createdAt(message.getCreatedAt())
                .build();
    }
    private static List<ReferencedChunkResponse> parseReferences(String json) {
        if (json == null || json.isBlank()) return List.of();
        try { return new com.fasterxml.jackson.databind.ObjectMapper().readValue(json,
                new com.fasterxml.jackson.core.type.TypeReference<List<ReferencedChunkResponse>>() {}); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new IllegalStateException("Invalid stored citations", e); }
    }
}
