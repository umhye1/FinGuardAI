package com.finguard.analysis.dto.response;

import com.finguard.keyword.domain.RiskKeyword;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class DetectedKeywordResponse {
    private String keyword;
    private String category;
    private int score;

    public static DetectedKeywordResponse from(RiskKeyword riskKeyword) {
        return DetectedKeywordResponse.builder()
                .keyword(riskKeyword.getKeyword())
                .category(riskKeyword.getCategory().getLabel())
                .score(riskKeyword.getRiskScore())
                .build();
    }
}
