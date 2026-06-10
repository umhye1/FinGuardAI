package com.finguard.analysis.domain;

import com.finguard.user.domain.User;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.ColumnTransformer;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Entity
@Table(name = "analysis_logs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class AnalysisLog {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "analysis_logs_seq_generator")
    @SequenceGenerator(
            name = "analysis_logs_seq_generator",
            sequenceName = "analysis_logs_seq",
            allocationSize = 1
    )
    @Column(name = "analysis_id")
    private Long analysisId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "input_text", nullable = false, columnDefinition = "TEXT")
    private String inputText;

    @Enumerated(EnumType.STRING)
    @Column(name = "risk_level", nullable = false, length = 20)
    private RiskLevel riskLevel;

    @Column(name = "risk_score", nullable = false)
    private int riskScore;

    @JdbcTypeCode(SqlTypes.JSON)
    @ColumnTransformer(write = "?::jsonb")
    @Column(name = "detected_keywords", columnDefinition = "jsonb")
    private String detectedKeywords;

    @Column(name = "rule_reason", columnDefinition = "TEXT")
    private String ruleReason;

    @Column(name = "ai_summary", columnDefinition = "TEXT")
    private String aiSummary;

    @Column(name = "recommended_action", columnDefinition = "TEXT")
    private String recommendedAction;

    @CreationTimestamp
    @Column(name = "created_at",  nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
