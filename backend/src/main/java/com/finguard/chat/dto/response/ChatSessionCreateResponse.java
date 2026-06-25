package com.finguard.chat.dto.response;

import com.finguard.chat.domain.ChatSession;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ChatSessionCreateResponse {

    private Long sessionId;
    private String title;
    private LocalDateTime createdAt;


    public static ChatSessionCreateResponse from(ChatSession chatSession) {
        return ChatSessionCreateResponse.builder()
                .sessionId(chatSession.getSessionId())
                .title(chatSession.getTitle())
                .createdAt(chatSession.getCreatedAt())
                .build();
    }
}
