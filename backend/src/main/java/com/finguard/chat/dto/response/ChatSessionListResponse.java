package com.finguard.chat.dto.response;

import com.finguard.chat.domain.ChatMessage;
import com.finguard.chat.domain.ChatSession;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ChatSessionListResponse {
    private Long sessionId;
    private String title;
    private String lastMessage;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public static ChatSessionListResponse of(ChatSession chatSession, ChatMessage lastMessage) {
        return ChatSessionListResponse.builder()
                .sessionId(chatSession.getSessionId())
                .title(chatSession.getTitle())
                .lastMessage(lastMessage != null ? lastMessage.getMessage() : null)
                .createdAt(chatSession.getCreatedAt())
                .updatedAt(chatSession.getUpdatedAt())
                .build();
    }

}
