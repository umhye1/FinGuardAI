package com.finguard.job.domain;

import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "processing_jobs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ProcessingJob {
    public enum Status { PENDING, RUNNING, COMPLETED, FAILED }
    @Id private UUID jobId;
    @Column(nullable = false) private Long documentId;
    @Column(nullable = false) private Long ownerId;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private Status status;
    @Column(nullable = false) private int attempts;
    private String errorCode;
    private UUID leaseToken;
    private Instant leaseUntil;
    @Column(nullable = false) private Instant createdAt;
    @Column(nullable = false) private Instant updatedAt;

    public ProcessingJob(Long documentId, Long ownerId) {
        this.jobId = UUID.randomUUID(); this.documentId = documentId; this.ownerId = ownerId;
        this.status = Status.PENDING; this.createdAt = Instant.now(); this.updatedAt = createdAt;
    }
    public UUID claim(Instant now, long leaseSeconds) {
        status = Status.RUNNING; attempts++; leaseToken = UUID.randomUUID();
        leaseUntil = now.plusSeconds(leaseSeconds); updatedAt = now;
        return leaseToken;
    }
    public boolean ownsLease(UUID token) { return status == Status.RUNNING && token.equals(leaseToken); }
    public void complete() { status = Status.COMPLETED; errorCode = null; finish(); }
    public void fail(String code) { status = Status.FAILED; errorCode = code; finish(); }
    private void finish() { leaseUntil = null; leaseToken = null; updatedAt = Instant.now(); }
}
