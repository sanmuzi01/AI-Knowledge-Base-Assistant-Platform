package com.enterprisehub.oa.dto;

import com.enterprisehub.oa.LeaveRequest;
import com.enterprisehub.oa.LeaveType;

import java.time.Instant;
import java.time.LocalDate;

public record LeaveRequestDto(
        long id,
        long applicantUserId,
        Long teamId,
        String leaveTypeCode,
        LocalDate startDate,
        LocalDate endDate,
        double days,
        String reason,
        String status,
        Long approverUserId,
        String decisionNote,
        Instant createdAt,
        Instant submittedAt,
        Instant decidedAt
) {
    public static LeaveRequestDto from(LeaveRequest r, LeaveType type) {
        return new LeaveRequestDto(
                r.getId(), r.getApplicantUserId(), r.getTeamId(), type.getCode(),
                r.getStartDate(), r.getEndDate(), r.getDays(), r.getReason(),
                r.getStatus().name(), r.getApproverUserId(), r.getDecisionNote(),
                r.getCreatedAt(), r.getSubmittedAt(), r.getDecidedAt()
        );
    }
}
