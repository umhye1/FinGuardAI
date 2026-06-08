package com.finguard.keyword.dto.response;

import com.finguard.keyword.domain.KeywordCategory;
import com.finguard.keyword.domain.RiskKeyword;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class KeywordResponse {
    private Long keywordId;
    private String keyword;
    private int riskScore;
    private KeywordCategory category;
    private String description;
    private boolean active;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public static KeywordResponse from(RiskKeyword riskKeyword) {
        return KeywordResponse.builder()
                .keywordId(riskKeyword.getKeyword_id())
                .keyword(riskKeyword.getKeyword())
                .riskScore(riskKeyword.getRiskScore())
                .category(riskKeyword.getCategory())
                .description(riskKeyword.getDescription())
                .active(riskKeyword.isActive())
                .createdAt(riskKeyword.getCreated_at())
                .updatedAt(riskKeyword.getUpdated_at())
                .build();
    }
}
