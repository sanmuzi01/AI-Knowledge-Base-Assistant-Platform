package com.enterprisehub.oa.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.LocalDate;

public record CreateLeaveDraftRequest(
        @NotBlank String leaveTypeCode,
        @NotNull LocalDate startDate,
        @NotNull LocalDate endDate,
        String reason
) {
}
