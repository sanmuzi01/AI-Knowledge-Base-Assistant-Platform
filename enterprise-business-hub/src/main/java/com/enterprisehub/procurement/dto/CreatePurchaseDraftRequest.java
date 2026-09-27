package com.enterprisehub.procurement.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Positive;

import java.util.List;

public record CreatePurchaseDraftRequest(@NotEmpty @Valid List<LineItem> lines) {
    public record LineItem(@NotBlank String sku, @Positive int quantity) {
    }
}
