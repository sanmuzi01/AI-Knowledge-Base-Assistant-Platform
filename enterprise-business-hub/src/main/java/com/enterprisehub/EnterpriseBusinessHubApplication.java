package com.enterprisehub;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 企业业务中心：OA/ERP-lite/CRM 业务闭环，供 FastAPI AI Agent 平台的部门 Agent 调用。
 * 见仓库根目录 docs/enterprise-business-hub-plan.md。
 *
 * 有意放在包根 com.enterprisehub（不是某个子包）：Spring Boot 默认按主类所在包
 * 递归扫描组件/JPA repository/entity，放子包会漏掉其它子包（oa/security/idempotency/
 * audit 等）——之前踩过这个坑，第一次起服务时所有 Controller 都 404。
 */
@SpringBootApplication
public class EnterpriseBusinessHubApplication {
    public static void main(String[] args) {
        SpringApplication.run(EnterpriseBusinessHubApplication.class, args);
    }
}
