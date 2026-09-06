package com.finguard.review.repository;
import com.finguard.review.domain.AnalysisReview;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.domain.*;
public interface AnalysisReviewRepository extends JpaRepository<AnalysisReview, Long> {
    boolean existsByAnalysisIdAndSubmittedBy(Long analysisId, Long submittedBy);
    Page<AnalysisReview> findByStatus(AnalysisReview.Status status, Pageable pageable);
}
