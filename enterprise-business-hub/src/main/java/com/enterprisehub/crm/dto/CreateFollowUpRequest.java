package com.enterprisehub.crm.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateFollowUpRequest(@NotBlank @Size(max = 1000) String content) {
}
