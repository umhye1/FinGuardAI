package com.finguard.analysis.dto.response;

import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.domain.RiskLevel;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class AnalysisDetailResponse {

    private Long analysisId;
    private String inputText;
    private RiskLevel riskLevel;
    private int riskScore;
    private List<DetectedKeywordResponse> detectedKeywordRespons;

    private String ruleReason;
    private String aiSummary;
    private String recommendedAction;
    private LocalDateTime createdAt;

    public static AnalysisDetailResponse of(
            AnalysisLog analysisLog,
            List<DetectedKeywordResponse> detectedKeywordResponses
    ){
        return AnalysisDetailResponse.builder()
                .analysisId(analysisLog.getAnalysisId())
                .inputText(analysisLog.getInputText())
                .riskLevel(analysisLog.getRiskLevel())
                .riskScore(analysisLog.getRiskScore())
                .detectedKeywordRespons(detectedKeywordResponses)
                .ruleReason(analysisLog.getRuleReason())
                .aiSummary(analysisLog.getAiSummary())
                .recommendedAction(analysisLog.getRecommendedAction())
                .createdAt(analysisLog.getCreatedAt())
                .build();

    }
}
