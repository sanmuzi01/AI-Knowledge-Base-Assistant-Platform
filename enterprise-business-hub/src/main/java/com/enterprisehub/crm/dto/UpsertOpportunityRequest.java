package com.enterprisehub.crm.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;

/** `opportunityId` 不填就创建新商机，填了就更新那一条（设计稿"创建或更新商机"）。 */
public record UpsertOpportunityRequest(Long opportunityId, @NotBlank String stage, @NotNull BigDecimal amount) {
}
