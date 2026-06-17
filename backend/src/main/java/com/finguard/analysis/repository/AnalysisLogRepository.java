package com.finguard.analysis.repository;

import com.finguard.analysis.domain.AnalysisLog;
import com.finguard.analysis.domain.RiskLevel;
import com.finguard.user.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface AnalysisLogRepository extends JpaRepository<AnalysisLog, Long> {

    List<AnalysisLog> findByUserOrderByCreatedAtDesc(User user);

    Optional<AnalysisLog> findByAnalysisIdAndUser(Long analysisId, User user);

    // 최신순 조회
    List<AnalysisLog> findAllByOrderByCreatedAtDesc();

    long countByRiskLevelIn(List<RiskLevel> riskLevels);

    long countByCreatedAtBetween(LocalDateTime start, LocalDateTime end);

}
