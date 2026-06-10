package com.finguard.analysis.dto.response;

import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.domain.RiskLevel;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class AnalysisResponse {

    private Long analysisId;
    private RiskLevel riskLevel;
    private int riskScore;
    private List<DetectedKeywordResponse> detectedKeywordRespons;

    private String ruleReason;
    private String aiSummary;
    private String recommendedAction;
    private LocalDateTime createdAt;

    public static AnalysisResponse of(
            AnalysisLog analysisLog,
            List<DetectedKeywordResponse> detectedKeywordResponse
    ){
        return AnalysisResponse.builder()
                .analysisId(analysisLog.getAnalysisId())
                .riskLevel(analysisLog.getRiskLevel())
                .riskScore(analysisLog.getRiskScore())
                .detectedKeywordRespons(detectedKeywordResponse)
                .ruleReason(analysisLog.getRuleReason())
                .aiSummary(analysisLog.getAiSummary())
                .recommendedAction(analysisLog.getRecommendedAction())
                .createdAt(analysisLog.getCreatedAt())
                .build();
    }

}
