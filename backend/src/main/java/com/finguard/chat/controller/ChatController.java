package com.finguard.chat.controller;

import com.finguard.chat.domain.ChatSession;
import com.finguard.chat.dto.request.ChatQuestionRequest;
import com.finguard.chat.dto.request.ChatSessionCreateRequest;
import com.finguard.chat.dto.response.ChatAnswerResponse;
import com.finguard.chat.dto.response.ChatMessageResponse;
import com.finguard.chat.dto.response.ChatSessionCreateResponse;
import com.finguard.chat.dto.response.ChatSessionListResponse;
import com.finguard.chat.repository.ChatSessionRepository;
import com.finguard.chat.service.ChatService;
import com.finguard.global.response.CommonResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    // 채팅 세션 생성
    @PostMapping("/sessions")
    public ResponseEntity<CommonResponse<ChatSessionCreateResponse>> createSession(
            @RequestBody ChatSessionCreateRequest request
    ) {
        ChatSessionCreateResponse response = chatService.createSession(request);

        return ResponseEntity.status(201)
                .body(CommonResponse.success(
                        201,
                        "채팅 세션이 생성되었습니다.",
                        response
                ));
    }


    @GetMapping("/sessions")
    public ResponseEntity<CommonResponse<List<ChatSessionListResponse>>> getSessions() {
        List<ChatSessionListResponse> response = chatService.getSessions();
        return ResponseEntity.ok(
                CommonResponse.success(
                        200,
                        "채팅 세션 목록 조회에 성공했습니다.",
                        response
                )
        );
    }

    @GetMapping("/sessions/{sessionId}/messages")
    public ResponseEntity<CommonResponse<List<ChatMessageResponse>>> getMessages(
            @PathVariable Long sessionId
    ){
        List<ChatMessageResponse> response = chatService.getMessages(sessionId);

        return ResponseEntity.ok(
                CommonResponse.success(
                        200,
                        "채팅 메시지 조회에 성공했습니다.",
                        response
                )
        );
    }

    // 질문 전송, AI 답변 생성
    @PostMapping("/sessions/{sessionId}/messages")
    public ResponseEntity<CommonResponse<ChatAnswerResponse>> askQuestion(
            @PathVariable Long sessionId,
            @RequestBody ChatQuestionRequest request
    ){
        ChatAnswerResponse response = chatService.askQuestion(sessionId, request);

        return ResponseEntity.ok(
                CommonResponse.success(
                        200,
                        "답변이 생성되었습니다.",
                        response
                )
        );
    }


    // 채팅 세션 삭제
    @DeleteMapping("sessions/{sessionId}")
    public ResponseEntity<CommonResponse<Void>> deleteSession(
            @PathVariable Long sessionId
    ){
        chatService.deleteSession(sessionId);

        return ResponseEntity.ok(
                CommonResponse.success("채팅 세션이 삭제되었습니다.")

        );
    }

}
