package com.enterprisehub.oa.dto;

public record LeaveBalanceDto(String leaveTypeCode, String leaveTypeName, double remainingDays, int year) {
}
