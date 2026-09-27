package com.enterprisehub.procurement;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.math.BigDecimal;

@Entity
@Table(name = "department_budget", uniqueConstraints = {
        @UniqueConstraint(name = "uq_department_budget_team_year", columnNames = {"team_id", "year"})
})
public class DepartmentBudget {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "team_id", nullable = false)
    private long teamId;

    @Column(name = "year", nullable = false)
    private int year;

    @Column(name = "remaining_amount", nullable = false, precision = 14, scale = 2)
    private BigDecimal remainingAmount;

    protected DepartmentBudget() {
    }

    public DepartmentBudget(long teamId, int year, BigDecimal remainingAmount) {
        this.teamId = teamId;
        this.year = year;
        this.remainingAmount = remainingAmount;
    }

    public Long getId() {
        return id;
    }

    public long getTeamId() {
        return teamId;
    }

    public int getYear() {
        return year;
    }

    public BigDecimal getRemainingAmount() {
        return remainingAmount;
    }

    public void deduct(BigDecimal amount) {
        this.remainingAmount = this.remainingAmount.subtract(amount);
    }
}
