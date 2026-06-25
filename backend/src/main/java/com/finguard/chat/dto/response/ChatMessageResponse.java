package com.finguard.chat.dto.response;

import com.finguard.chat.domain.ChatMessage;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class ChatMessageResponse {
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
                .referencedChunks(List.of())
                .createdAt(message.getCreatedAt())
                .build();
    }
}
