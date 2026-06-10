package com.finguard.analysis.domain;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum RiskLevel {
    SAFE("안전", "위험 요소가 거의 없습니다."),
    LOW("낮은 위험", "일부 주의가 필요합니다."),
    CAUTION("주의", "의심 요소가 확인되었습니다."),
    SUSPICIOUS("의심", "피싱 가능성이 있습니다."),
    WARNING("경고", "위험 징후가 뚜렷합니다."),
    DANGEROUS("위험", "피싱 위험 가능성이 높습니다."),
    HIGH_RISK("고위험", "강한 피싱 위험이 탐지되었습니다."),
    CRITICAL("매우 위험", "즉시 대응이 필요한 매우 위험한 문자입니다.");

    private final String label;
    private final String description;

    // 점수를 위험 등급으로 반환
    public static RiskLevel fromScore(int score) {
        if(score<10){
            return SAFE;
        }
        if (score < 25) {
            return LOW;
        }
        if (score < 40) {
            return CAUTION;
        }
        if (score < 55) {
            return SUSPICIOUS;
        }
        if (score < 70) {
            return WARNING;
        }
        if (score < 85) {
            return DANGEROUS;
        }
        if (score < 95) {
            return HIGH_RISK;
        }
        return CRITICAL;
    }

}
