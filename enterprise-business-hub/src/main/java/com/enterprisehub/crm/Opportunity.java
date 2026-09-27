package com.enterprisehub.crm;

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

@Entity
@Table(name = "opportunity")
public class Opportunity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "customer_id", nullable = false)
    private long customerId;

    @Enumerated(EnumType.STRING)
    @Column(name = "stage", nullable = false, length = 20)
    private OpportunityStage stage;

    @Column(name = "amount", nullable = false, precision = 14, scale = 2)
    private BigDecimal amount;

    @Column(name = "owner_user_id", nullable = false)
    private long ownerUserId;

    @Column(name = "team_id", nullable = false)
    private long teamId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Opportunity() {
    }

    public Opportunity(long customerId, OpportunityStage stage, BigDecimal amount, long ownerUserId, long teamId) {
        this.customerId = customerId;
        this.stage = stage;
        this.amount = amount;
        this.ownerUserId = ownerUserId;
        this.teamId = teamId;
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    public void update(OpportunityStage stage, BigDecimal amount) {
        this.stage = stage;
        this.amount = amount;
        this.updatedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public long getCustomerId() {
        return customerId;
    }

    public OpportunityStage getStage() {
        return stage;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public long getOwnerUserId() {
        return ownerUserId;
    }

    public long getTeamId() {
        return teamId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
