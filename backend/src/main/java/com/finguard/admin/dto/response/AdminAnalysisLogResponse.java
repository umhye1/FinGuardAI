package com.finguard.admin.dto.response;

import com.finguard.analysis.domain.AnalysisLog;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;



@Getter
@Builder
public class AdminAnalysisLogResponse {
    private Long analysisId;
    private UserSummary userSummary;
    private String inputPreview;
    private String riskLevel;
    private int riskScore;
    private LocalDateTime createdAt;

    public static AdminAnalysisLogResponse from(AnalysisLog analysisLog){
        return AdminAnalysisLogResponse.builder()
                .analysisId(analysisLog.getAnalysisId())
                .userSummary(
                        analysisLog.getUser() != null
                        ? UserSummary.from(analysisLog.getUser())
                                : null
                )
                .inputPreview(makePreview(analysisLog.getInputText()))
                .riskLevel(analysisLog.getRiskLevel().name())
                .riskScore(analysisLog.getRiskScore())
                .createdAt(analysisLog.getCreatedAt())
                .build();
    }

    private static String makePreview(String inputText) {
        if (inputText == null) {
            return "";
        }

        if (inputText.length() <= 30){
            return inputText;
        }

        return inputText.substring(0, 30) + "...";
    }
}
