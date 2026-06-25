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



    // 문서 기반 질문
    @Transactional
    public ChatAnswerResponse askQuestion(Long sessionId, ChatQuestionRequest request) {
        if(request.getQuestion() ==null || request.getQuestion().isBlank()) {
            throw new BadRequestException("질문 내용을 입력해주세요");
        }

        User user = getCurrentUser();

        ChatSession session = getSessionByIdAndUser(sessionId,user);

        ChatMessage userMessage = ChatMessage.builder()
                .session(session)
                .sender(MessageSender.USER)
                .message(request.getQuestion())
                .referencedChunks(null)
                .build();

        ChatMessage savedUserMessage = chatMessageRepository.save(userMessage);
        String dummyAnswer = "현재는 테스트 답변입니다. 추후 RAG 기반 답변으로 교체됩니다.";

        ChatMessage aiMessage = ChatMessage.builder()
                .session(session)
                .sender(MessageSender.AI)
                .message(dummyAnswer)
                .referencedChunks(null)
                .build();

        ChatMessage savedAiMessage = chatMessageRepository.save(aiMessage);
        return ChatAnswerResponse.of(savedUserMessage,savedAiMessage);
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
