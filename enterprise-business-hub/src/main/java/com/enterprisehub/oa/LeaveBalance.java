package com.enterprisehub.oa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(name = "leave_balance", uniqueConstraints = {
        @UniqueConstraint(name = "uq_leave_balance_user_type_year", columnNames = {"user_id", "leave_type_id", "year"})
})
public class LeaveBalance {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private long userId;

    @Column(name = "leave_type_id", nullable = false)
    private long leaveTypeId;

    @Column(name = "year", nullable = false)
    private int year;

    @Column(name = "remaining_days", nullable = false)
    private double remainingDays;

    protected LeaveBalance() {
    }

    public LeaveBalance(long userId, long leaveTypeId, int year, double remainingDays) {
        this.userId = userId;
        this.leaveTypeId = leaveTypeId;
        this.year = year;
        this.remainingDays = remainingDays;
    }

    public Long getId() {
        return id;
    }

    public long getUserId() {
        return userId;
    }

    public long getLeaveTypeId() {
        return leaveTypeId;
    }

    public int getYear() {
        return year;
    }

    public double getRemainingDays() {
        return remainingDays;
    }

    public void deduct(double days) {
        this.remainingDays -= days;
    }

    public void restore(double days) {
        this.remainingDays += days;
    }
}
