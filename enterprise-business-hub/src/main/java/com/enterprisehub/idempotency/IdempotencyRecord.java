package com.enterprisehub.idempotency;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/** 写操作的幂等记录：同一个 `Idempotency-Key` 第二次打过来，直接把第一次的结果原样返回，
 * 不重新执行业务逻辑——防止网络重试/用户连点造成重复请假单/重复采购单。 */
@Entity
@Table(name = "idempotency_record")
public class IdempotencyRecord {
    @Id
    @Column(name = "idempotency_key", length = 100)
    private String idempotencyKey;

    @Column(name = "status_code", nullable = false)
    private int statusCode;

    // 同 AuditEvent.detail 那条注释：不用 @Lob，避免 Hibernate 默认类型映射跟
    // Flyway 建的 MEDIUMTEXT 不一致。
    @Column(name = "response_body", columnDefinition = "MEDIUMTEXT")
    private String responseBody;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected IdempotencyRecord() {
    }

    public IdempotencyRecord(String idempotencyKey, int statusCode, String responseBody) {
        this.idempotencyKey = idempotencyKey;
        this.statusCode = statusCode;
        this.responseBody = responseBody;
        this.createdAt = Instant.now();
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public String getResponseBody() {
        return responseBody;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
