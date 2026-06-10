package com.finguard.analysis.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.domain.RiskLevel;
import com.finguard.analysis.dto.request.AnalysisRequest;
import com.finguard.analysis.dto.response.AnalysisDetailResponse;
import com.finguard.analysis.dto.response.AnalysisHistoryResponse;
import com.finguard.analysis.dto.response.AnalysisResponse;
import com.finguard.analysis.dto.response.DetectedKeywordResponse;
import com.finguard.analysis.repository.AnalysisLogRepository;
import com.finguard.global.exception.BadRequestException;
import com.finguard.global.exception.ForbiddenException;
import com.finguard.global.exception.NotFoundException;
import com.finguard.keyword.domain.RiskKeyword;
import com.finguard.keyword.repository.KeywordRepository;
import com.finguard.user.domain.User;
import com.finguard.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AnalysisService {

    private final AnalysisLogRepository analysisLogRepository; // 분석 결과 db 저장, 조회
    private final KeywordRepository keywordRepository; // 관리자가 등록한 위험 키워드를 db에서 가져올 떄 사용
    private final UserRepository userRepository; // 현재 로그인한 사용자 찾을 때 사용
    private final ObjectMapper objectMapper; // Java 객체를 JSON 문자열로 바꾸거나, JSON 문자열을 Java 객체로 다시 바꿀 때 사용


    // 1. 문자 분석하기 - 사용자가 보낸 문자를 분석하고, 결과를 DB에 저장한 뒤 응답으로 반환
    @Transactional
    public AnalysisResponse analyze(AnalysisRequest request) {
        // 1. 입력 문자 검증
        validateText(request.getText()); // 빈 문자 검증. 빈 문자열을 보낼 경우 분석 x

        // 2. 현재 로그인 사용자 조회
        User user = getCurrentUser(); // jwt 인증 정보 기반으로 현재 사용자 찾기

        // 3. 활성화된 위험 키워드 조회 (active = true)
        List<RiskKeyword> activateKeywords = keywordRepository.findByActiveTrue();

        // 4. 문자 안에 포함된 키워드 탐지
        // 사용자 입력 : [Web발신] 검찰청 사건 연루로 확인이 필요합니다. 아래 링크 접속 후 본인인증 바랍니다.
        // 에서 contains()로 키워드 포함 여부 검사
        List<DetectedKeywordResponse> detectedKeywords = activateKeywords.stream()
                .filter(keyword->request.getText().contains(keyword.getKeyword()))
                .map(DetectedKeywordResponse::from) // RiskKeyword 엔티티를 응답 DTO로 바꿈
                .toList();

        // 5. 위험 점수 합산 - 탐지된 키워드들의 점수를 더함
        int riskScore = detectedKeywords.stream()
                .mapToInt(DetectedKeywordResponse::getScore)
                .sum();

        // 6. 위험 등급 계산 - enum에서 점수를 등급으로 바꿈
        RiskLevel riskLevel = RiskLevel.fromScore(riskScore);

        // 7. 분석 사유/요약/대응 문구 생성 - 룰 기반으로 문구를 임시 생성 (AI 서버 연동 전)
        String ruleReason = createRuleReason(detectedKeywords);
        String aiSummary = createAiSummary(riskLevel);
        String recommendedAction = createRecommendedAction(riskLevel);

        // 8. 탐지 키워드 목록을 JSON으로 변환
        String detectedKeywordsJson= convertDetectedKeywordsToJson(detectedKeywords);

        // 9. AnalysisLog 저장
        AnalysisLog analysisLog = AnalysisLog.builder()
                .user(user)
                .inputText(request.getText())
                .riskLevel(riskLevel)
                .riskScore(riskScore)
                .detectedKeywords(detectedKeywordsJson)
                .ruleReason(ruleReason)
                .aiSummary(aiSummary)
                .recommendedAction(recommendedAction)
                .build();
        AnalysisLog savedAnalysisLog = analysisLogRepository.saveAndFlush(analysisLog);

        // 10. AnalysisResponse 반환
        return AnalysisResponse.of(savedAnalysisLog,detectedKeywords);
    }


    // 문자열 검증
    private void validateText(String text) {
        if (text == null || text.trim().isEmpty()) {
            throw new BadRequestException("분석할 문자를 입력해주세요.");
        }
    }

    // 현재 로그인한 사용자 정보 가져오기
    private User getCurrentUser() {
        // jwt 필터에서 인증 성공하면 Spring Security가 현재 사용자 정보를 SecurityContextHolder에 저장해둠.
        // SecurityContextHolder에서 email을 꺼내옴
        String email = SecurityContextHolder.getContext().getAuthentication().getName();

        // db에서 email 정보를 기반으로 User(사용자)를 찾음
        return userRepository.findByEmail(email)
                .orElseThrow(()-> new NotFoundException("사용자를 찾을 수 없습니다."));
    }

    // 탐지된 키워드들의 카테고리를 모아서 분석 사유를 만드는 메서드
    private String createRuleReason(List<DetectedKeywordResponse> detectedKeywords) {
        if(detectedKeywords.isEmpty()){
            return "위험 키워드가 탐지되지 않았습니다.";
        }
        String categories = detectedKeywords.stream()
                .map(DetectedKeywordResponse::getCategory)
                .distinct()
                .reduce((a,b) -> a + ", " + b)
                .orElse("");

        return categories+ " 패턴이 탐지되었습니다.";
    }

    // 요약 - 위험 등급에 따라 고정 문구를 반환
    // 후에 FastAPI 붙이면 이 부분을 AI 서버 응답으로 바꿀 것.
    private String createAiSummary(RiskLevel riskLevel) {
        return switch (riskLevel){
            case SAFE -> "현재 문자에서는 뚜렷한 피싱 위험 요소가 확인되지 않았습니다.";
            case LOW -> "일부 주의가 필요한 표현이 포함되어 있습니다.";
            case CAUTION -> "의심 요소가 확인되어 추가 확인이 필요합니다.";
            case SUSPICIOUS -> "피싱 가능성이 있는 표현이 포함되어 있습니다.";
            case WARNING -> "위험 징후가 뚜렷한 문자입니다.";
            case DANGEROUS -> "피싱 위험 가능성이 높은 문자입니다.";
            case HIGH_RISK -> "공공기관 또는 금융기관을 사칭한 피싱 가능성이 높습니다.";
            case CRITICAL -> "즉시 대응이 필요한 매우 위험한 문자로 판단됩니다.";
        };
    }

    // 위험 등급에 따라 사용자에게 대응 방법을 안내
    private String createRecommendedAction(RiskLevel riskLevel) {
        return switch (riskLevel) {
            case SAFE, LOW -> "불필요한 링크 클릭은 피하고, 의심스러운 경우 공식 채널을 통해 확인하세요.";
            case CAUTION, SUSPICIOUS -> "문자 내 링크를 클릭하지 말고, 발신 기관의 공식 홈페이지나 고객센터를 통해 확인하세요.";
            case WARNING, DANGEROUS -> "링크 클릭 및 개인정보 입력을 중단하고, 금융회사 또는 관련 기관에 직접 확인하세요.";
            case HIGH_RISK, CRITICAL -> "링크를 클릭하지 말고, 피해가 의심되면 즉시 금융회사 고객센터 또는 경찰청 112에 신고하세요.";
        };
    }

    // 탐지된 키워드 리스트를 JSON 문자열로 바꿔서 DB에 저장
    private String convertDetectedKeywordsToJson(List<DetectedKeywordResponse> detectedKeywords) {
        try{
            return objectMapper.writeValueAsString(detectedKeywords);
        }catch (JsonProcessingException e){
            throw new IllegalStateException("탐지 키워드 변환 중 오류가 발생했습니다.",e);
        }
    }



    // 2. 분석 이력 목록 검색하기
    public List<AnalysisHistoryResponse> getHistories(){
        // 1) 현재 로그인한 사용자 조회
        User user = getCurrentUser();

        // 2) 그 사용자의 분석 이력 조회
        return analysisLogRepository.findByUserOrderByCreatedAtDesc(user) // 3) 최신순 정렬
                .stream()
                .map(AnalysisHistoryResponse::from) // AnalysisHistoryResponse로 변환
                .toList();
    }

    // 3. 분석 상세 조회하기
    public AnalysisDetailResponse getDetail(Long analysisId){
        // 1) 현재 로그인한 사용자 조회
        User user = getCurrentUser();

        // 2) analysisId, user로 분석 결과 조회
        AnalysisLog analysisLog = analysisLogRepository.findByAnalysisIdAndUser(analysisId,user)
                .orElseThrow(()-> new ForbiddenException("해당 분석 결과에 접근할 권한이 없습니다."));

        // 3) DB에 저장된 JSONB 문자열을 다시 List 로 변환하기
        List<DetectedKeywordResponse> detectedKeywords =
                convertJsonToDetectedKeywords(analysisLog.getDetectedKeywords());

        // 5) 상세 응답 DTO반환
        return AnalysisDetailResponse.of(analysisLog, detectedKeywords);
    }

    private List<DetectedKeywordResponse> convertJsonToDetectedKeywords(String detectedKeywordsJson) {
        try{
            if (detectedKeywordsJson == null || detectedKeywordsJson.isBlank()) {
                return List.of();
            }
            return objectMapper.readValue(
                    detectedKeywordsJson, new TypeReference<List<DetectedKeywordResponse>>() {}
            );
        }catch (JsonProcessingException e){
            throw new IllegalStateException("탐지 키워드 조회 중 오류가 발생했습니다.",e);
        }
    }

    // 4. 분석 이력 삭제하기
    @Transactional
    public void deleteAnalysis(Long analysisId) {
        // 1) 현재 로그인한 사용자 조회
        User user = getCurrentUser();

        // 2) analysisId, user로 분석 결과 조회
        AnalysisLog analysisLog = analysisLogRepository.findByAnalysisIdAndUser(analysisId,user)
                .orElseThrow(()-> new ForbiddenException("해당 분석 결과에 접근할 권한이 없습니다."));

        // 3) 맞으면 삭제
        analysisLogRepository.delete(analysisLog);
    }



}
