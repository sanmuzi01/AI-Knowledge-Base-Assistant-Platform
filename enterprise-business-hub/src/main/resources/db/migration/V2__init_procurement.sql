-- 采购闭环（docs/enterprise-business-hub-plan.md 第4节）。
-- 第一版不做财务总账/税务/生产制造/供应链全模块，产品和库存合并成一张表
-- （不单独建 Inventory 表），够用就行，不为了"看起来完整"而过度建模。

CREATE TABLE product (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(40) NOT NULL,
    name VARCHAR(120) NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT '个',
    unit_price DECIMAL(12,2) NOT NULL,
    on_hand_qty INT NOT NULL DEFAULT 0,
    safety_stock_qty INT NOT NULL DEFAULT 0,
    supplier_code VARCHAR(40) NULL,
    UNIQUE KEY uq_product_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE department_budget (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    team_id BIGINT NOT NULL,
    year INT NOT NULL,
    remaining_amount DECIMAL(14,2) NOT NULL,
    UNIQUE KEY uq_department_budget_team_year (team_id, year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_request (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    requester_user_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
    approver_user_id BIGINT NULL,
    decision_note VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    submitted_at DATETIME NULL,
    decided_at DATETIME NULL,
    KEY idx_purchase_request_requester (requester_user_id, created_at),
    KEY idx_purchase_request_team_status (team_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_request_line (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    purchase_request_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    KEY idx_purchase_line_request (purchase_request_id),
    CONSTRAINT fk_purchase_line_request FOREIGN KEY (purchase_request_id) REFERENCES purchase_request(id),
    CONSTRAINT fk_purchase_line_product FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_order (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    purchase_request_id BIGINT NOT NULL,
    supplier_code VARCHAR(40) NULL,
    supplier_name VARCHAR(120) NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uq_purchase_order_request (purchase_request_id),
    CONSTRAINT fk_purchase_order_request FOREIGN KEY (purchase_request_id) REFERENCES purchase_request(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
