package com.finguard.chat.service;

import com.finguard.chat.domain.ChatMessage;
import com.finguard.chat.domain.ChatSession;
import com.finguard.chat.domain.MessageSender;
import com.finguard.chat.dto.request.ChatQuestionRequest;
import com.finguard.chat.dto.request.ChatSessionCreateRequest;
import com.finguard.chat.dto.response.ChatAnswerResponse;
import com.finguard.chat.dto.response.ChatMessageResponse;
import com.finguard.chat.dto.response.ChatSessionCreateResponse;
import com.finguard.chat.dto.response.ChatSessionListResponse;
import com.finguard.chat.repository.ChatMessageRepository;
import com.finguard.chat.repository.ChatSessionRepository;
import com.finguard.global.exception.BadRequestException;
import com.finguard.global.exception.NotFoundException;
import com.finguard.user.domain.User;
import com.finguard.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ChatService {

    private final ChatMessageRepository chatMessageRepository;
    private final ChatSessionRepository chatSessionRepository;
    private final UserRepository userRepository;
    private final com.finguard.ai.service.RagClient ragClient;
    private final ChatAnswerWriter answerWriter;


    // 세션 생성
    @Transactional
    public ChatSessionCreateResponse createSession(ChatSessionCreateRequest request) {
        if(request.getTitle() == null || request.getTitle().isBlank()) {

            throw new BadRequestException("채팅 세션 제목을 입력해주세요");
        }
        User user = getCurrentUser();

        ChatSession session = ChatSession.builder()
                .user(user)
                .title(request.getTitle())
                .build();

        ChatSession savedSession = chatSessionRepository.save(session);

        return ChatSessionCreateResponse.from(savedSession);
    }



    // 세션 조회 (채팅 목록 조회)
    public List<ChatSessionListResponse> getSessions(){
        User user = getCurrentUser();

        return chatSessionRepository.findByUserAndDeletedFalseOrderByUpdatedAtDesc(user)
                .stream()
                .map(session -> {
                    ChatMessage lastMessage = chatMessageRepository
                            .findTopBySessionOrderByCreatedAtDesc(session)
                            .orElse(null);
                    return ChatSessionListResponse.of(session, lastMessage);
                }).toList();
    }


    // 채팅 메시지 조회
    public List<ChatMessageResponse> getMessages(Long sessionId){
        User user = getCurrentUser();
        ChatSession session = getSessionByIdAndUser(sessionId, user);

        return chatMessageRepository.findBySessionOrderByCreatedAtAsc(session)
                .stream()
                .map(ChatMessageResponse::from)
                .toList();
    }



    // AI network calls are outside the database transaction. Ownership is checked again on save.
    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.NOT_SUPPORTED)
    public ChatAnswerResponse askQuestion(Long sessionId, ChatQuestionRequest request) {
        if (request.getQuestion() == null || request.getQuestion().isBlank() || request.getQuestion().length() > 10000) {
            throw new BadRequestException("질문은 1~10000자로 입력해주세요.");
        }
        User user = getCurrentUser();
        getSessionByIdAndUser(sessionId, user);
        var result = ragClient.answer(request.getQuestion());
        return answerWriter.save(user.getEmail(), sessionId, request.getQuestion(), result);
    }

    // 세션 삭제
    @Transactional
    public void deleteSession(Long sessionId) {
        User user = getCurrentUser();
        ChatSession session = getSessionByIdAndUser(sessionId,user);

        session.delete();
    }


    private ChatSession getSessionByIdAndUser(Long sessionId, User user) {
        return chatSessionRepository.findBySessionIdAndUserAndDeletedFalse(sessionId, user)
                .orElseThrow(() -> new NotFoundException("채팅 세션을 찾을 수 없습니다."));
    }

    private User getCurrentUser() {
        String email = SecurityContextHolder.getContext()
                .getAuthentication()
                .getName();

        return userRepository.findByEmail(email)
                .orElseThrow(() -> new NotFoundException("사용자를 찾을 수 없습니다."));
    }
}
