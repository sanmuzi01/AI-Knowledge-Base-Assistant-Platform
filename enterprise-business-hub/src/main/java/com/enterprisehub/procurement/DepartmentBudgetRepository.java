package com.enterprisehub.procurement;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface DepartmentBudgetRepository extends JpaRepository<DepartmentBudget, Long> {
    Optional<DepartmentBudget> findByTeamIdAndYear(long teamId, int year);
}
