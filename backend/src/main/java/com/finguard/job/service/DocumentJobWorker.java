package com.finguard.job.service;

import com.finguard.document.service.DocumentTextExtractor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
@ConditionalOnProperty(name = "jobs.worker.enabled", havingValue = "true", matchIfMissing = true)
public class DocumentJobWorker {
    private final DocumentJobService jobs;
    private final DocumentTextExtractor extractor;

    @Scheduled(fixedDelayString = "${jobs.worker.delay-ms:2000}")
    public void poll() {
        jobs.claim().ifPresent(work -> {
            if (work.attempt() > 3) { jobs.fail(work, "RETRY_EXHAUSTED"); return; }
            try {
                String text = extractor.extract(work.filePath());
                jobs.complete(work, text);
            } catch (Exception e) {
                log.warn("Document processing failed: jobId={}, cause={}", work.jobId(), e.getClass().getSimpleName());
                jobs.fail(work, "DOCUMENT_PROCESSING_FAILED");
            }
        });
    }
}
