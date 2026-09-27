package com.enterprisehub.crm;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface FollowUpRepository extends JpaRepository<FollowUp, Long> {
    List<FollowUp> findByCustomerIdOrderByCreatedAtDesc(long customerId);
}
