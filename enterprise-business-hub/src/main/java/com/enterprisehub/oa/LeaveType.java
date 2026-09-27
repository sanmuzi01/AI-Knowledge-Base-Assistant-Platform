package com.enterprisehub.oa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "leave_type")
public class LeaveType {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "code", nullable = false, unique = true, length = 30)
    private String code;

    @Column(name = "name", nullable = false, length = 60)
    private String name;

    @Column(name = "default_annual_days", nullable = false)
    private int defaultAnnualDays;

    protected LeaveType() {
    }

    public LeaveType(String code, String name, int defaultAnnualDays) {
        this.code = code;
        this.name = name;
        this.defaultAnnualDays = defaultAnnualDays;
    }

    public Long getId() {
        return id;
    }

    public String getCode() {
        return code;
    }

    public String getName() {
        return name;
    }

    public int getDefaultAnnualDays() {
        return defaultAnnualDays;
    }
}
