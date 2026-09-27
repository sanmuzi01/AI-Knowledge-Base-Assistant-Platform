-- 只在 db 容器第一次初始化（数据卷为空）时执行一次，给企业业务中心
-- （enterprise-business-hub）建它自己的库；agent_sql 由 MYSQL_DATABASE 环境变量建。
CREATE DATABASE IF NOT EXISTS enterprise_business CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
