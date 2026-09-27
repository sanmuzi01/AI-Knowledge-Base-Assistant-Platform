package com.enterprisehub.procurement.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public record PurchaseRequestDto(
        long id,
        long requesterUserId,
        long teamId,
        String status,
        BigDecimal totalAmount,
        List<LineDto> lines,
        Long approverUserId,
        String decisionNote,
        Instant createdAt,
        Instant submittedAt,
        Instant decidedAt,
        PurchaseOrderDto purchaseOrder
) {
    public record LineDto(String sku, String productName, int quantity, BigDecimal unitPrice) {
    }

    public record PurchaseOrderDto(String supplierCode, String supplierName, String status) {
    }
}
