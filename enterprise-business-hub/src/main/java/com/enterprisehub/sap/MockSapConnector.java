package com.enterprisehub.sap;

import org.springframework.stereotype.Component;

import java.util.Map;

/** 演示用的假 SAP：几个内置供应商代码返回固定数据，其余代码返回"未找到"，不报错。
 * 第一版只覆盖"查供应商"+"健康检查"——生成采购单是本地的 `PurchaseOrder`，不经过
 * SAP 的采购单接口（真实企业接入时如果需要双向同步单据，再扩展这个接口）。 */
@Component
public class MockSapConnector implements SapConnector {
    private static final Map<String, String> KNOWN_SUPPLIERS = Map.of(
            "SUP-001", "华东电子元件有限公司",
            "SUP-002", "京津办公用品供应商",
            "SUP-003", "南方物流设备制造"
    );

    @Override
    public SupplierInfo getSupplier(String supplierCode) {
        String name = KNOWN_SUPPLIERS.get(supplierCode);
        if (name == null) {
            return new SupplierInfo(supplierCode, "未知供应商（Mock 数据里没有）", false);
        }
        return new SupplierInfo(supplierCode, name, true);
    }

    @Override
    public HealthStatus healthCheck() {
        return new HealthStatus(true, "mock connector 始终健康");
    }
}
