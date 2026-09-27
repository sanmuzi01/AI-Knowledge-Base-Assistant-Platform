package com.enterprisehub.crm;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "customer")
public class Customer {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "name", nullable = false, length = 120)
    private String name;

    @Column(name = "industry", length = 60)
    private String industry;

    @Column(name = "owner_user_id", nullable = false)
    private long ownerUserId;

    @Column(name = "team_id", nullable = false)
    private long teamId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected Customer() {
    }

    public Customer(String name, String industry, long ownerUserId, long teamId) {
        this.name = name;
        this.industry = industry;
        this.ownerUserId = ownerUserId;
        this.teamId = teamId;
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getIndustry() {
        return industry;
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
}
