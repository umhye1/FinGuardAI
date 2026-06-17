package com.finguard.audit.service;

import com.finguard.audit.domain.AuditAction;
import com.finguard.audit.domain.AuditLog;
import com.finguard.audit.domain.AuditTargetType;
import com.finguard.audit.repository.AuditLogRepository;
import com.finguard.user.domain.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AuditLogService {

    private final AuditLogRepository auditLogRepository;

    @Transactional
    public void saveLog(
            User user,
            AuditAction action,
            AuditTargetType targetType,
            Long targetId,
            String ipAddress,
            String detail
    ) {

        AuditLog auditLog = AuditLog.builder()
                .user(user)
                .action(action)
                .targetType(targetType)
                .targetId(targetId)
                .ipAddress(ipAddress)
                .detail(detail)
                .build();

        auditLogRepository.save(auditLog);
    }
}
