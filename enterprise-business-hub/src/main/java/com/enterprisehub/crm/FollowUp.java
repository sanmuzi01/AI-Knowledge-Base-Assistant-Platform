package com.enterprisehub.crm;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/** 跟进记录：草稿 -> 确认两步，没有审批环节——设计稿里 CRM 本来就没提部门负责人
 * 审批这一步，用户确认自己的跟进内容就够了。 */
@Entity
@Table(name = "follow_up")
public class FollowUp {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "customer_id", nullable = false)
    private long customerId;

    @Column(name = "author_user_id", nullable = false)
    private long authorUserId;

    @Column(name = "content", nullable = false, length = 1000)
    private String content;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private FollowUpStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "confirmed_at")
    private Instant confirmedAt;

    protected FollowUp() {
    }

    public FollowUp(long customerId, long authorUserId, String content) {
        this.customerId = customerId;
        this.authorUserId = authorUserId;
        this.content = content;
        this.status = FollowUpStatus.DRAFT;
        this.createdAt = Instant.now();
    }

    public void confirm() {
        this.status = FollowUpStatus.CONFIRMED;
        this.confirmedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public long getCustomerId() {
        return customerId;
    }

    public long getAuthorUserId() {
        return authorUserId;
    }

    public String getContent() {
        return content;
    }

    public FollowUpStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getConfirmedAt() {
        return confirmedAt;
    }
}
