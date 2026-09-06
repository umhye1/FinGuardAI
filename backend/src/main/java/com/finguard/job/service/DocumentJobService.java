package com.finguard.job.service;

import com.finguard.document.domain.*;
import com.finguard.document.repository.*;
import com.finguard.document.service.DocumentChunkService;
import com.finguard.global.exception.*;
import com.finguard.job.domain.ProcessingJob;
import com.finguard.job.repository.ProcessingJobRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.data.domain.PageRequest;
import java.time.Instant;
import java.util.*;

@Service
@RequiredArgsConstructor
public class DocumentJobService {
    private final ProcessingJobRepository jobs;
    private final DocumentRepository documents;
    private final DocumentChunkRepository chunks;
    private final DocumentChunkService chunkService;
    public record Work(UUID jobId, Long documentId, UUID leaseToken, int attempt, String filePath) {}

    @Transactional
    public UUID enqueue(Long documentId, Long ownerId) {
        Document document = documents.findLocked(documentId).orElseThrow(() -> new NotFoundException("문서를 찾을 수 없습니다."));
        if (jobs.existsByDocumentIdAndStatusIn(documentId, List.of(ProcessingJob.Status.PENDING, ProcessingJob.Status.RUNNING))) {
            throw new ConflictException("이미 처리 중인 문서입니다.");
        }
        document.updateStatus(DocumentStatus.PROCESSING);
        return jobs.save(new ProcessingJob(documentId, ownerId)).getJobId();
    }

    @Transactional
    public Optional<Work> claim() {
        List<ProcessingJob> candidates = jobs.findClaimable(Instant.now(), PageRequest.of(0, 1));
        if (candidates.isEmpty()) return Optional.empty();
        ProcessingJob job = candidates.getFirst();
        UUID token = job.claim(Instant.now(), 300);
        Document doc = documents.findById(job.getDocumentId()).orElseThrow();
        return Optional.of(new Work(job.getJobId(), job.getDocumentId(), token, job.getAttempts(), doc.getFilePath()));
    }

    @Transactional
    public void complete(Work work, String text) {
        Document doc = documents.findLocked(work.documentId()).orElseThrow();
        ProcessingJob job = jobs.findLocked(work.jobId()).orElseThrow();
        if (!job.ownsLease(work.leaseToken())) return;
        if (text == null || text.isBlank()) throw new IllegalArgumentException("EMPTY_TEXT");
        chunks.deleteByDocument(doc);
        chunks.flush();
        int count = chunkService.createChunks(doc, text);
        doc.completeProcessing(count);
        job.complete();
    }

    @Transactional
    public void fail(Work work, String code) {
        Document doc = documents.findLocked(work.documentId()).orElseThrow();
        ProcessingJob job = jobs.findLocked(work.jobId()).orElseThrow();
        if (!job.ownsLease(work.leaseToken())) return;
        job.fail(code);
        doc.failProcessing();
    }
}
