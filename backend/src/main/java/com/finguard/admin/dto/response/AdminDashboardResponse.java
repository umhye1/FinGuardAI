package com.finguard.admin.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class AdminDashboardResponse {
    private long totalAnalysisCount;
    private long highRiskCount;
    private long mediumRiskCount;
    private long lowRiskCount;
    private long documentCount;
    private long keywordCount;
    private long todayAnalysisCount;
}
