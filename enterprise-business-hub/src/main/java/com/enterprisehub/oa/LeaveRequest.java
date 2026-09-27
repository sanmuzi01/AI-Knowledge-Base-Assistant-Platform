package com.enterprisehub.oa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "leave_request")
public class LeaveRequest {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "applicant_user_id", nullable = false)
    private long applicantUserId;

    @Column(name = "team_id")
    private Long teamId;

    @Column(name = "leave_type_id", nullable = false)
    private long leaveTypeId;

    @Column(name = "start_date", nullable = false)
    private LocalDate startDate;

    @Column(name = "end_date", nullable = false)
    private LocalDate endDate;

    @Column(name = "days", nullable = false)
    private double days;

    @Column(name = "reason", length = 500)
    private String reason;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private LeaveStatus status;

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

    protected LeaveRequest() {
    }

    public LeaveRequest(long applicantUserId, Long teamId, long leaveTypeId, LocalDate startDate,
                         LocalDate endDate, double days, String reason) {
        this.applicantUserId = applicantUserId;
        this.teamId = teamId;
        this.leaveTypeId = leaveTypeId;
        this.startDate = startDate;
        this.endDate = endDate;
        this.days = days;
        this.reason = reason;
        this.status = LeaveStatus.DRAFT;
        this.createdAt = Instant.now();
    }

    public void submit() {
        this.status = LeaveStatus.SUBMITTED;
        this.submittedAt = Instant.now();
    }

    public void approve(long approverUserId, String note) {
        this.status = LeaveStatus.APPROVED;
        this.approverUserId = approverUserId;
        this.decisionNote = note;
        this.decidedAt = Instant.now();
    }

    public void reject(long approverUserId, String note) {
        this.status = LeaveStatus.REJECTED;
        this.approverUserId = approverUserId;
        this.decisionNote = note;
        this.decidedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public long getApplicantUserId() {
        return applicantUserId;
    }

    public Long getTeamId() {
        return teamId;
    }

    public long getLeaveTypeId() {
        return leaveTypeId;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }

    public double getDays() {
        return days;
    }

    public String getReason() {
        return reason;
    }

    public LeaveStatus getStatus() {
        return status;
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
