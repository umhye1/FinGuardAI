package com.finguard.job.controller;
import com.finguard.global.exception.NotFoundException;
import com.finguard.global.response.CommonResponse;
import com.finguard.job.domain.ProcessingJob;
import com.finguard.job.repository.ProcessingJobRepository;
import com.finguard.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.time.Instant;
import java.util.UUID;

@RestController
@RequestMapping("/api/jobs")
@RequiredArgsConstructor
public class JobController {
    private final ProcessingJobRepository jobs;
    private final UserRepository users;
    public record JobResponse(UUID jobId, Long documentId, ProcessingJob.Status status, int attempts,
                              String errorCode, Instant createdAt, Instant updatedAt) {}
    @GetMapping("/{id}")
    public CommonResponse<JobResponse> get(@PathVariable UUID id, Authentication auth) {
        ProcessingJob job = jobs.findById(id).orElseThrow(() -> new NotFoundException("작업을 찾을 수 없습니다."));
        Long userId = users.findByEmail(auth.getName()).orElseThrow().getUserId();
        boolean admin = auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        if (!admin && !job.getOwnerId().equals(userId)) throw new NotFoundException("작업을 찾을 수 없습니다.");
        return CommonResponse.success("작업 조회에 성공했습니다.", new JobResponse(job.getJobId(), job.getDocumentId(),
                job.getStatus(), job.getAttempts(), job.getErrorCode(), job.getCreatedAt(), job.getUpdatedAt()));
    }
}
