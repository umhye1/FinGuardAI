package com.finguard.analysis.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AnalysisRequest {

    @jakarta.validation.constraints.NotBlank
    @jakarta.validation.constraints.Size(max = 10000)
    private String text;
}
