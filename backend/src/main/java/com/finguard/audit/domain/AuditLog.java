package com.finguard.audit.domain;

import com.finguard.user.domain.User;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "audit_logs")
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AuditLog {

    @Id
    @GeneratedValue(strategy =  GenerationType.SEQUENCE, generator = "audit_logs_seq_generator")
    @SequenceGenerator(
            name = "audit_logs_seq_generator",
            sequenceName = "audit_logs_seq",
            allocationSize = 1
    )
    @Column(name = "audit_id")
    private Long auditId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Enumerated(EnumType.STRING)
    @Column(name = "action", nullable = false,length = 50)
    private AuditAction action;

    @Enumerated(EnumType.STRING)
    @Column(name = "target_type", nullable = false,length = 50)
    private AuditTargetType targetType;


    @Column(name = "target_id")
    private Long targetId;

    @Column(name = "ip_address", length = 100)
    private String ipAddress;

    @Column(name = "detail", columnDefinition = "TEXT")
    private String detail;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

}
