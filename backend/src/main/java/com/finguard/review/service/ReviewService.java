package com.finguard.review.service;
import com.finguard.review.domain.AnalysisReview;
import com.finguard.review.repository.AnalysisReviewRepository;
import com.finguard.analysis.repository.AnalysisLogRepository;
import com.finguard.user.repository.UserRepository;
import com.finguard.global.exception.*;
import com.finguard.ai.service.PrivacyMasker;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.data.domain.*;

@Service
@RequiredArgsConstructor
public class ReviewService {
    private final AnalysisReviewRepository reviews;
    private final AnalysisLogRepository analyses;
    private final UserRepository users;
    private final PrivacyMasker masker;
    @Transactional
    public AnalysisReview submit(String email, Long analysisId, AnalysisReview.FeedbackType type, String comment) {
        var user = users.findByEmail(email).orElseThrow();
        analyses.findByAnalysisIdAndUser(analysisId, user).orElseThrow(() -> new NotFoundException("분석을 찾을 수 없습니다."));
        if (reviews.existsByAnalysisIdAndSubmittedBy(analysisId, user.getUserId())) throw new ConflictException("이미 피드백을 제출했습니다.");
        try { return reviews.saveAndFlush(new AnalysisReview(analysisId, user.getUserId(), type, comment == null ? null : masker.mask(comment))); }
        catch (org.springframework.dao.DataIntegrityViolationException e) { throw new ConflictException("이미 제출되었거나 삭제된 분석입니다."); }
    }
    @Transactional(readOnly = true)
    public Page<AnalysisReview> list(AnalysisReview.Status status, int page, int size) {
        if (page < 0 || size < 1 || size > 100) throw new BadRequestException("페이지 범위가 올바르지 않습니다.");
        return reviews.findByStatus(status, PageRequest.of(page, size, Sort.by("createdAt").descending().and(Sort.by("reviewId").descending())));
    }
    @Transactional
    public AnalysisReview review(String email, Long id, Long version, AnalysisReview.Label label, String reason) {
        var review = reviews.findById(id).orElseThrow(() -> new NotFoundException("검토 건을 찾을 수 없습니다."));
        if (!review.getVersion().equals(version)) throw new ConflictException("변경된 검토 건입니다. 다시 조회해주세요.");
        review.review(users.findByEmail(email).orElseThrow().getUserId(), label, masker.mask(reason));
        return reviews.saveAndFlush(review);
    }
}
