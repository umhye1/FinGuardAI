package com.finguard.admin.service;

import com.finguard.admin.dto.response.AdminAnalysisLogResponse;
import com.finguard.admin.dto.response.AdminDashboardResponse;
import com.finguard.admin.dto.response.AuditLogResponse;
import com.finguard.analysis.domain.RiskLevel;
import com.finguard.analysis.repository.AnalysisLogRepository;
import com.finguard.audit.domain.AuditLog;
import com.finguard.audit.repository.AuditLogRepository;
import com.finguard.document.repository.DocumentRepository;
import com.finguard.document.service.DocumentService;
import com.finguard.keyword.repository.KeywordRepository;
import com.finguard.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@Transactional(readOnly = true)
@RequiredArgsConstructor
public class AdminService {

    private final AuditLogRepository auditLogRepository;
    private final AnalysisLogRepository analysisLogRepository;
    private final DocumentRepository documentRepository;
    private final KeywordRepository keywordRepository;

    // 감사 로그 조회 - 최신순으로 가져옴
    public List<AuditLogResponse> getAuditLogs() {
        return auditLogRepository.findAllByOrderByCreatedAtDesc()
                .stream()
                .map(AuditLogResponse::from)
                .toList();
    }

    // 전체 분석 로그 - 최신순
    public List<AdminAnalysisLogResponse> getAnalysisLogs() {
        return analysisLogRepository.findAllByOrderByCreatedAtDesc()
                .stream()
                .map(AdminAnalysisLogResponse::from)
                .toList();
    }

    // 대시보드 통계 조회 - 최신순
    public AdminDashboardResponse getDashboard() {
        LocalDateTime startOfToday = LocalDateTime.now();
        LocalDateTime startOfTomorrow = startOfToday.plusDays(1);

        return AdminDashboardResponse.builder()
                .totalAnalysisCount(analysisLogRepository.count())
                .lowRiskCount(
                        analysisLogRepository.countByRiskLevelIn(
                                List.of(
                                        RiskLevel.SAFE,
                                        RiskLevel.LOW
                                )
                        )
                )
                .mediumRiskCount(
                        analysisLogRepository.countByRiskLevelIn(
                            List.of(
                                    RiskLevel.CAUTION,
                                    RiskLevel.SUSPICIOUS,
                                    RiskLevel.WARNING
                            )
                        )
                )
                .highRiskCount(
                        analysisLogRepository.countByRiskLevelIn(
                                List.of(
                                        RiskLevel.DANGEROUS,
                                        RiskLevel.HIGH_RISK,
                                        RiskLevel.CRITICAL
                                )
                        )
                )
                .documentCount(documentRepository.count())
                .keywordCount(keywordRepository.countByActiveTrue())
                .todayAnalysisCount(
                        analysisLogRepository.countByCreatedAtBetween(
                                startOfToday,
                                startOfTomorrow
                        )
                )
                .build();
    }

}
