package com.finguard.keyword.dto.request;

import com.finguard.keyword.domain.KeywordCategory;
import com.finguard.keyword.domain.RiskKeyword;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class KeywordUpdateRequest {
    private String keyword;
    private int riskScore;
    private KeywordCategory category;
    private String description;
    private boolean active;

}
