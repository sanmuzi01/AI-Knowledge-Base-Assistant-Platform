package com.enterprisehub.sap;

/**
 * SAP 处理方式（docs/enterprise-business-hub-plan.md 第5节）：不自建复制，只定义接口。
 * 演示阶段用 {@link MockSapConnector}；真实企业提供接口后新写一个 RealSapConnector 实现
 * 这个接口、换掉 Spring 装配的 Bean（{@code @Primary} 或 profile），Agent 端和
 * `ProcurementService` 都不需要改一行代码。
 */
public interface SapConnector {
    SupplierInfo getSupplier(String supplierCode);

    HealthStatus healthCheck();

    record SupplierInfo(String code, String name, boolean active) {
    }

    record HealthStatus(boolean healthy, String detail) {
    }
}
