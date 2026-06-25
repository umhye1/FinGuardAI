package com.finguard.chat.repository;

import com.finguard.chat.domain.ChatMessage;
import com.finguard.chat.domain.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {

    List<ChatMessage> findBySessionOrderByCreatedAtAsc(ChatSession session);

    Optional<ChatMessage> findTopBySessionOrderByCreatedAtDesc(ChatSession session);
}
