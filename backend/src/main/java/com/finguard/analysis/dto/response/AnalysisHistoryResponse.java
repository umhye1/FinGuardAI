package com.finguard.analysis.dto.response;


import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.domain.RiskLevel;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class AnalysisHistoryResponse {

    private Long analysisId;
    private String inputPreview;
    private RiskLevel riskLevel;
    private int riskScore;
    private LocalDateTime createdAt;

    public static AnalysisHistoryResponse from(AnalysisLog analysisLog){
        return AnalysisHistoryResponse.builder()
                .analysisId(analysisLog.getAnalysisId())
                .inputPreview(makePreview(analysisLog.getInputText()))
                .riskLevel(analysisLog.getRiskLevel())
                .riskScore(analysisLog.getRiskScore())
                .createdAt(analysisLog.getCreatedAt())
                .build();
    }

    private static String makePreview(String inputText) {
        if(inputText == null){
            return "";
        }

        if(inputText.length()<30){
            return inputText;
        }
        return inputText.substring(0,30) + "...";
    }
}
