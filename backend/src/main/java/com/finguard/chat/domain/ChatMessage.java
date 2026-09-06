package com.finguard.chat.domain;

import jakarta.persistence.*;
import jakarta.websocket.Session;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.springframework.boot.actuate.autoconfigure.wavefront.WavefrontProperties;

import java.time.LocalDateTime;

@Entity
@Table(name = "chat_messages")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ChatMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "chat_messages_seq_generator")
    @SequenceGenerator(
            name = "chat_messages_seq_generator",
            sequenceName = "chat_messages_seq",
            allocationSize = 1
    )
    @Column(name = "message_id")
    private Long messageId;


    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id",nullable = false)
    private ChatSession session;

    @Enumerated(EnumType.STRING)
    @Column(name = "sender", nullable = false, length = 20)
    private MessageSender sender;

    @Column(name = "message", nullable = false, columnDefinition = "TEXT")
    private String message;

    @Column(name ="referenced_chunks",columnDefinition = "TEXT")
    private String referencedChunks;

    @Column(length = 30) private String generationStatus;
    @Column(length = 100) private String modelVersion;
    @Column(length = 100) private String promptVersion;

    public void setGenerationMetadata(String status, String model, String prompt) {
        generationStatus = status; modelVersion = model; promptVersion = prompt;
    }

    @CreationTimestamp
    @Column(name="created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Builder
    public ChatMessage(
            ChatSession session,
            MessageSender sender,
            String message,
            String referencedChunks
    ) {
        this.session = session;
        this.sender = sender;
        this.message = message;
        this.referencedChunks = referencedChunks;
    }





}
