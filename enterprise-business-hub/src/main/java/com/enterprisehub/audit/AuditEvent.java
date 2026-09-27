package com.enterprisehub.audit;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/** 业务审计：只追加，没有 update/delete 方法——跟 FastAPI 侧 audit_event 是同一个模式，
 * 分别落在各自的库里（这边归业务中心自己管，不共库）。 */
@Entity
@Table(name = "audit_event")
public class AuditEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private long userId;

    @Column(name = "action", nullable = false, length = 60)
    private String action;

    @Column(name = "resource_type", length = 40)
    private String resourceType;

    @Column(name = "resource_id")
    private Long resourceId;

    // 不用 @Lob——Hibernate 对 String + @Lob 的默认 JDBC 类型映射跟 Flyway 建的 MEDIUMTEXT
    // 不是同一种（validate 模式下会报 schema 不一致），直接用 columnDefinition 对齐实际列类型。
    @Column(name = "detail", columnDefinition = "MEDIUMTEXT")
    private String detail;

    @Column(name = "trace_id", length = 64)
    private String traceId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected AuditEvent() {
    }

    public AuditEvent(long userId, String action, String resourceType, Long resourceId, String detail, String traceId) {
        this.userId = userId;
        this.action = action;
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        this.detail = detail;
        this.traceId = traceId;
        this.createdAt = Instant.now();
    }
}
