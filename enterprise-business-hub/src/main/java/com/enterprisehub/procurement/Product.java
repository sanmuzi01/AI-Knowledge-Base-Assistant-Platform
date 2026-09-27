package com.enterprisehub.procurement;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;

/** 产品 + 库存合一（第一版不单独建 Inventory 表，见 V2 迁移文件注释）。 */
@Entity
@Table(name = "product")
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "sku", nullable = false, unique = true, length = 40)
    private String sku;

    @Column(name = "name", nullable = false, length = 120)
    private String name;

    @Column(name = "unit", nullable = false, length = 20)
    private String unit = "个";

    @Column(name = "unit_price", nullable = false, precision = 12, scale = 2)
    private BigDecimal unitPrice;

    @Column(name = "on_hand_qty", nullable = false)
    private int onHandQty;

    @Column(name = "safety_stock_qty", nullable = false)
    private int safetyStockQty;

    @Column(name = "supplier_code", length = 40)
    private String supplierCode;

    protected Product() {
    }

    public Product(String sku, String name, String unit, BigDecimal unitPrice,
                   int onHandQty, int safetyStockQty, String supplierCode) {
        this.sku = sku;
        this.name = name;
        this.unit = unit;
        this.unitPrice = unitPrice;
        this.onHandQty = onHandQty;
        this.safetyStockQty = safetyStockQty;
        this.supplierCode = supplierCode;
    }

    public boolean isBelowSafetyStock() {
        return onHandQty < safetyStockQty;
    }

    public Long getId() {
        return id;
    }

    public String getSku() {
        return sku;
    }

    public String getName() {
        return name;
    }

    public String getUnit() {
        return unit;
    }

    public BigDecimal getUnitPrice() {
        return unitPrice;
    }

    public int getOnHandQty() {
        return onHandQty;
    }

    public int getSafetyStockQty() {
        return safetyStockQty;
    }

    public String getSupplierCode() {
        return supplierCode;
    }
}
