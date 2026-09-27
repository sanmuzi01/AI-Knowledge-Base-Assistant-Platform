package com.enterprisehub.crm.dto;

import com.enterprisehub.crm.FollowUp;

import java.time.Instant;

public record FollowUpDto(long id, long customerId, String content, String status,
                           Instant createdAt, Instant confirmedAt) {
    public static FollowUpDto from(FollowUp f) {
        return new FollowUpDto(f.getId(), f.getCustomerId(), f.getContent(), f.getStatus().name(),
                f.getCreatedAt(), f.getConfirmedAt());
    }
}
