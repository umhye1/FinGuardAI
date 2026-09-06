package com.finguard.analysis.service;
import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.repository.AnalysisLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
@RequiredArgsConstructor
public class AnalysisLogWriter {
    private final AnalysisLogRepository logs;
    @Transactional public AnalysisLog save(AnalysisLog log) { return logs.saveAndFlush(log); }
}
