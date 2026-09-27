package com.enterprisehub.procurement;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/** 采购单：审批通过后生成，供应商信息来自 SapConnector（Mock/Real）。 */
@Entity
@Table(name = "purchase_order")
public class PurchaseOrder {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "purchase_request_id", nullable = false, unique = true)
    private long purchaseRequestId;

    @Column(name = "supplier_code", length = 40)
    private String supplierCode;

    @Column(name = "supplier_name", length = 120)
    private String supplierName;

    @Column(name = "status", nullable = false, length = 20)
    private String status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected PurchaseOrder() {
    }

    public PurchaseOrder(long purchaseRequestId, String supplierCode, String supplierName, String status) {
        this.purchaseRequestId = purchaseRequestId;
        this.supplierCode = supplierCode;
        this.supplierName = supplierName;
        this.status = status;
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public long getPurchaseRequestId() {
        return purchaseRequestId;
    }

    public String getSupplierCode() {
        return supplierCode;
    }

    public String getSupplierName() {
        return supplierName;
    }

    public String getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
