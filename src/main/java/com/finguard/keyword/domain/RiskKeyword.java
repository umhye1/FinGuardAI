package com.finguard.keyword.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "phishing_keywords")
public class RiskKeyword {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "keyword_id")
    private Long keyword_id;     // 키워드 ID

    @Column(name = "keyword", nullable = false, unique = true)
    private String keyword;  // 위험 키워드

    @Column(name = "risk_score", nullable = false)
    private int riskScore; // 위험 점수

    @Enumerated(EnumType.STRING)
    @Column(name = "category", nullable = false)
    private KeywordCategory category;   // 기관사칭, 금전요구 등

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;// 설명

    @Column(name = "active", nullable = false)
    private boolean active; // 사용 여부

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime created_at;// 생성일

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updated_at; //수정일

    public void update(String keyword, int riskScore, KeywordCategory category, String description, boolean active) {
        this.keyword = keyword;
        this.riskScore = riskScore;
        this.category = category;
        this.description = description;
        this.active = active;
    }

    public void deactivate() {
        this.active = false;
    }

}
