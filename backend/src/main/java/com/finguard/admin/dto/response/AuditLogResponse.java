package com.finguard.admin.dto.response;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finguard.audit.domain.AuditLog;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.Map;

@Getter
@Builder
public class AuditLogResponse {
    private Long auditId;
    private Long userId;
    private String action;
    private String targetType;
    private Long targetId;
    private String ipAddress;
    private Map<String, Object> detail;
    private LocalDateTime createdAt;

    private static final ObjectMapper objectMapper = new ObjectMapper();

    public static AuditLogResponse from(AuditLog auditLog) {
        return AuditLogResponse.builder()
                .auditId(auditLog.getAuditId())
                .userId(
                        auditLog.getUser() != null
                            ? auditLog.getUser().getUserId()
                                : null
                )
                .action(auditLog.getAction().name())
                .targetType(auditLog.getTargetType().name())
                .targetId(auditLog.getTargetId())
                .ipAddress(auditLog.getIpAddress())
                .detail(parseDetail(auditLog.getDetail()))
                .createdAt(auditLog.getCreatedAt())
                .build();

    }

    private static Map<String, Object> parseDetail(String detail) {
        try{
            if(detail == null || detail.isBlank()) {
                return Map.of();
            }
            return objectMapper.readValue(
                    detail,
                    new TypeReference<Map<String, Object>>() {}
            );
        }catch (Exception e) {
            return Map.of("message",detail);
        }
    }
}
