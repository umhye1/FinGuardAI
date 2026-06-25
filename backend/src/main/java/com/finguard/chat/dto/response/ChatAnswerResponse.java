package com.finguard.chat.dto.response;

import com.finguard.chat.domain.ChatMessage;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ChatAnswerResponse {

    private ChatMessageResponse userMessage;
    private ChatMessageResponse aiMessage;

    public static ChatAnswerResponse of(ChatMessage userMessage, ChatMessage aiMessage) {
        return ChatAnswerResponse.builder()
                .userMessage(ChatMessageResponse.from(userMessage))
                .aiMessage(ChatMessageResponse.from(aiMessage))
                .build();
    }
}