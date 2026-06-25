package com.finguard.chat.repository;

import com.finguard.chat.domain.ChatSession;
import com.finguard.user.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {

    List<ChatSession> findByUserAndDeletedFalseOrderByUpdatedAtDesc(User user);

    Optional<ChatSession> findBySessionIdAndUserAndDeletedFalse(Long sessionId, User user);

}
