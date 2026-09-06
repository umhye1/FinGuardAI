package com.finguard.review.controller;
import com.finguard.review.domain.AnalysisReview;
import com.finguard.review.service.ReviewService;
import com.finguard.global.response.CommonResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.security.Principal;
import java.time.Instant;
import java.util.List;

@RestController
@RequiredArgsConstructor
public class ReviewController {
    private final ReviewService reviews;
    public record FeedbackRequest(@NotNull AnalysisReview.FeedbackType type, @Size(max = 1000) String comment) {}
    public record ReviewRequest(@NotNull @PositiveOrZero Long version, @NotNull AnalysisReview.Label label,
                                @NotBlank @Size(max = 1000) String reason) {}
    public record ReviewResponse(Long reviewId, Long analysisId, AnalysisReview.FeedbackType feedbackType,
        String comment, AnalysisReview.Status status, AnalysisReview.Label label, String reason,
        Long reviewedBy, Instant createdAt, Instant reviewedAt, Long version) {
        static ReviewResponse from(AnalysisReview r) {
            return new ReviewResponse(r.getReviewId(), r.getAnalysisId(), r.getFeedbackType(), r.getComment(), r.getStatus(),
                    r.getLabel(), r.getReason(), r.getReviewedBy(), r.getCreatedAt(), r.getReviewedAt(), r.getVersion());
        }
    }
    public record ReviewPage(List<ReviewResponse> content, int page, int size, long totalElements) {}
    @PostMapping("/api/analysis/{id}/feedback")
    public ResponseEntity<CommonResponse<ReviewResponse>> feedback(@PathVariable Long id, @Valid @RequestBody FeedbackRequest request, Principal user) {
        var result = reviews.submit(user.getName(), id, request.type(), request.comment());
        return ResponseEntity.status(201).body(CommonResponse.success(201, "피드백을 접수했습니다.", ReviewResponse.from(result)));
    }
    @GetMapping("/api/admin/reviews")
    public CommonResponse<ReviewPage> list(@RequestParam(defaultValue = "PENDING") AnalysisReview.Status status,
            @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size) {
        var result = reviews.list(status, page, size);
        return CommonResponse.success("검토 목록입니다.", new ReviewPage(result.map(ReviewResponse::from).getContent(), page, size, result.getTotalElements()));
    }
    @PatchMapping("/api/admin/reviews/{id}")
    public CommonResponse<ReviewResponse> review(@PathVariable Long id, @Valid @RequestBody ReviewRequest request, Principal user) {
        return CommonResponse.success("검토를 저장했습니다.", ReviewResponse.from(reviews.review(user.getName(), id, request.version(), request.label(), request.reason())));
    }
}
