package com.enterprisehub.crm.dto;

import com.enterprisehub.crm.Opportunity;

import java.math.BigDecimal;
import java.time.Instant;

public record OpportunityDto(long id, long customerId, String stage, BigDecimal amount,
                              long ownerUserId, long teamId, Instant createdAt, Instant updatedAt) {
    public static OpportunityDto from(Opportunity o) {
        return new OpportunityDto(o.getId(), o.getCustomerId(), o.getStage().name(), o.getAmount(),
                o.getOwnerUserId(), o.getTeamId(), o.getCreatedAt(), o.getUpdatedAt());
    }
}
