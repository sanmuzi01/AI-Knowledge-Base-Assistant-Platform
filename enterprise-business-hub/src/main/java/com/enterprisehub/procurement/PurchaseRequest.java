package com.enterprisehub.procurement;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.Instant;

/** 采购申请单头。明细在 {@link PurchaseRequestLine}（独立表 + repository，不用
 * JPA 级联管理，见它的类注释）。 */
@Entity
@Table(name = "purchase_request")
public class PurchaseRequest {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "requester_user_id", nullable = false)
    private long requesterUserId;

    @Column(name = "team_id", nullable = false)
    private long teamId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private PurchaseStatus status;

    @Column(name = "total_amount", nullable = false, precision = 14, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "approver_user_id")
    private Long approverUserId;

    @Column(name = "decision_note", length = 500)
    private String decisionNote;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "submitted_at")
    private Instant submittedAt;

    @Column(name = "decided_at")
    private Instant decidedAt;

    protected PurchaseRequest() {
    }

    public PurchaseRequest(long requesterUserId, long teamId, BigDecimal totalAmount) {
        this.requesterUserId = requesterUserId;
        this.teamId = teamId;
        this.totalAmount = totalAmount;
        this.status = PurchaseStatus.DRAFT;
        this.createdAt = Instant.now();
    }

    public void submit() {
        this.status = PurchaseStatus.SUBMITTED;
        this.submittedAt = Instant.now();
    }

    public void approve(long approverUserId, String note) {
        this.status = PurchaseStatus.APPROVED;
        this.approverUserId = approverUserId;
        this.decisionNote = note;
        this.decidedAt = Instant.now();
    }

    public void reject(long approverUserId, String note) {
        this.status = PurchaseStatus.REJECTED;
        this.approverUserId = approverUserId;
        this.decisionNote = note;
        this.decidedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public long getRequesterUserId() {
        return requesterUserId;
    }

    public long getTeamId() {
        return teamId;
    }

    public PurchaseStatus getStatus() {
        return status;
    }

    public BigDecimal getTotalAmount() {
        return totalAmount;
    }

    public Long getApproverUserId() {
        return approverUserId;
    }

    public String getDecisionNote() {
        return decisionNote;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getSubmittedAt() {
        return submittedAt;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }
}
