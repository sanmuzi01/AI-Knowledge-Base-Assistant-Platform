-- 迁移：background_task 表加 重试机制 字段
-- 执行：mysql -u root -p agent_sql < sql/alter_background_task_retry.sql
-- 或在 MySQL 客户端直接执行下面两条

ALTER TABLE background_task
    ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT '本任务被重试过的次数',
    ADD COLUMN parent_task_id INT NULL COMMENT '重试时指向触发本次重试的原任务ID';

ALTER TABLE background_task
    ADD CONSTRAINT fk_task_parent FOREIGN KEY (parent_task_id)
    REFERENCES background_task(id) ON DELETE SET NULL;
