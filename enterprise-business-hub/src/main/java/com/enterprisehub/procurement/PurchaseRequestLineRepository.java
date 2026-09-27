package com.enterprisehub.procurement;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PurchaseRequestLineRepository extends JpaRepository<PurchaseRequestLine, Long> {
    List<PurchaseRequestLine> findByPurchaseRequestId(long purchaseRequestId);
}
