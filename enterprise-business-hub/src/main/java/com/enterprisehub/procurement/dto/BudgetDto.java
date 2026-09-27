package com.enterprisehub.procurement.dto;

import com.enterprisehub.procurement.DepartmentBudget;

import java.math.BigDecimal;

public record BudgetDto(long teamId, int year, BigDecimal remainingAmount) {
    public static BudgetDto from(DepartmentBudget b) {
        return new BudgetDto(b.getTeamId(), b.getYear(), b.getRemainingAmount());
    }
}
