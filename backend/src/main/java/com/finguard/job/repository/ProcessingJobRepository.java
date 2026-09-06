package com.finguard.job.repository;
import com.finguard.job.domain.ProcessingJob;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Pageable;
import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.*;

public interface ProcessingJobRepository extends JpaRepository<ProcessingJob, UUID> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select j from ProcessingJob j where j.status = 'PENDING' or (j.status = 'RUNNING' and j.leaseUntil < :now) order by j.createdAt")
    List<ProcessingJob> findClaimable(@Param("now") Instant now, Pageable page);
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select j from ProcessingJob j where j.jobId = :id")
    Optional<ProcessingJob> findLocked(@Param("id") UUID id);
    boolean existsByDocumentIdAndStatusIn(Long documentId, Collection<ProcessingJob.Status> statuses);
    void deleteByDocumentId(Long documentId);
}
