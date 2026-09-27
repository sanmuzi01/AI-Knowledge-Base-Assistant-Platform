-- CRM 客户跟进闭环（docs/enterprise-business-hub-plan.md 第4节）。
-- 没有审批环节（跟 OA/采购不一样，设计稿里 CRM 本来就没提"部门负责人审批"这一步），
-- 只有"草稿 -> 确认"两步，用户自己确认自己的跟进记录，不需要别人批准。

CREATE TABLE customer (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    industry VARCHAR(60) NULL,
    owner_user_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_customer_team (team_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE contact (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    name VARCHAR(80) NOT NULL,
    title VARCHAR(60) NULL,
    phone VARCHAR(30) NULL,
    email VARCHAR(120) NULL,
    KEY idx_contact_customer (customer_id),
    CONSTRAINT fk_contact_customer FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE follow_up (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    author_user_id BIGINT NOT NULL,
    content VARCHAR(1000) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    confirmed_at DATETIME NULL,
    KEY idx_follow_up_customer (customer_id, created_at),
    CONSTRAINT fk_follow_up_customer FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE opportunity (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    stage VARCHAR(20) NOT NULL,
    amount DECIMAL(14,2) NOT NULL DEFAULT 0,
    owner_user_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    KEY idx_opportunity_customer (customer_id),
    CONSTRAINT fk_opportunity_customer FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
