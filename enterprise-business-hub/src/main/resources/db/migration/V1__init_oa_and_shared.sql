-- OA 请假闭环 + 共享的幂等/审计表（docs/enterprise-business-hub-plan.md 第4/6节）。
-- 表结构变更都走这里的新增迁移文件，不允许改这个已发布的文件（同主项目 Alembic 的约定）。

CREATE TABLE leave_type (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(30) NOT NULL,
    name VARCHAR(60) NOT NULL,
    default_annual_days INT NOT NULL,
    UNIQUE KEY uq_leave_type_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leave_balance (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    leave_type_id BIGINT NOT NULL,
    year INT NOT NULL,
    remaining_days DOUBLE NOT NULL,
    UNIQUE KEY uq_leave_balance_user_type_year (user_id, leave_type_id, year),
    CONSTRAINT fk_leave_balance_type FOREIGN KEY (leave_type_id) REFERENCES leave_type(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leave_request (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    applicant_user_id BIGINT NOT NULL,
    team_id BIGINT NULL,
    leave_type_id BIGINT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days DOUBLE NOT NULL,
    reason VARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL,
    approver_user_id BIGINT NULL,
    decision_note VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    submitted_at DATETIME NULL,
    decided_at DATETIME NULL,
    KEY idx_leave_request_applicant (applicant_user_id, created_at),
    KEY idx_leave_request_team_status (team_id, status),
    CONSTRAINT fk_leave_request_type FOREIGN KEY (leave_type_id) REFERENCES leave_type(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE idempotency_record (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    status_code INT NOT NULL,
    response_body MEDIUMTEXT NULL,
    created_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_event (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    action VARCHAR(60) NOT NULL,
    resource_type VARCHAR(40) NULL,
    resource_id BIGINT NULL,
    detail MEDIUMTEXT NULL,
    trace_id VARCHAR(64) NULL,
    created_at DATETIME NOT NULL,
    KEY idx_audit_event_resource (resource_type, resource_id, created_at),
    KEY idx_audit_event_user (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO leave_type (code, name, default_annual_days) VALUES
    ('annual', '年假', 10),
    ('sick', '病假', 15),
    ('personal', '事假', 5);
