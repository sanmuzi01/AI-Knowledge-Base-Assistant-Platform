package com.enterprisehub.procurement.dto;

import com.enterprisehub.procurement.Product;

import java.math.BigDecimal;

public record ProductDto(String sku, String name, String unit, BigDecimal unitPrice,
                          int onHandQty, int safetyStockQty, boolean belowSafetyStock) {
    public static ProductDto from(Product p) {
        return new ProductDto(p.getSku(), p.getName(), p.getUnit(), p.getUnitPrice(),
                p.getOnHandQty(), p.getSafetyStockQty(), p.isBelowSafetyStock());
    }
}
