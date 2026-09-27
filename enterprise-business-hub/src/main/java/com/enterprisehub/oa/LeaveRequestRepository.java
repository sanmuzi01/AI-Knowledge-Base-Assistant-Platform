package com.enterprisehub.oa;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface LeaveRequestRepository extends JpaRepository<LeaveRequest, Long> {
    List<LeaveRequest> findByApplicantUserIdOrderByCreatedAtDesc(long applicantUserId);

    List<LeaveRequest> findByTeamIdAndStatusOrderByCreatedAtDesc(long teamId, LeaveStatus status);
}
