package com.enterprisehub.oa;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface LeaveBalanceRepository extends JpaRepository<LeaveBalance, Long> {
    Optional<LeaveBalance> findByUserIdAndLeaveTypeIdAndYear(long userId, long leaveTypeId, int year);

    List<LeaveBalance> findByUserIdAndYear(long userId, int year);
}
