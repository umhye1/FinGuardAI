package com.finguard.review.domain;
import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;

@Entity
@Table(name = "analysis_reviews", uniqueConstraints = @UniqueConstraint(columnNames = {"analysis_id", "submitted_by"}))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AnalysisReview {
    public enum Status { PENDING, REVIEWED }
    public enum FeedbackType { FALSE_POSITIVE, FALSE_NEGATIVE, INCORRECT_GUIDANCE, OTHER }
    public enum Label { PHISHING, NORMAL, UNCERTAIN }
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long reviewId;
    @Column(name = "analysis_id", nullable = false) private Long analysisId;
    @Column(name = "submitted_by", nullable = false) private Long submittedBy;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private FeedbackType feedbackType;
    @Column(length = 1000) private String comment;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private Status status;
    @Enumerated(EnumType.STRING) private Label label;
    private Long reviewedBy;
    @Column(length = 1000) private String reason;
    @Column(nullable = false) private Instant createdAt;
    private Instant reviewedAt;
    @Version private Long version;
    public AnalysisReview(Long analysisId, Long userId, FeedbackType type, String comment) {
        this.analysisId = analysisId; submittedBy = userId; feedbackType = type;
        this.comment = comment; status = Status.PENDING; createdAt = Instant.now();
    }
    public void review(Long reviewer, Label label, String reason) {
        this.reviewedBy = reviewer; this.label = label; this.reason = reason;
        status = Status.REVIEWED; reviewedAt = Instant.now();
    }
}
