package com.finguard.keyword.dto.request;

import com.finguard.keyword.domain.KeywordCategory;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class KeywordCreateRequest {

    private String keyword;
    private int riskScore;
    private KeywordCategory category;
    private String description;
}
