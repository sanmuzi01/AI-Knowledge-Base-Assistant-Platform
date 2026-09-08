# Database Migrations

这里是正式数据库迁移目录，用于逐步替代 `models/init_db.py` 中的 `create_all` 和手写幂等 `ALTER TABLE`。

当前阶段是兼容过渡：

- 已有数据库继续由现有启动逻辑兜底，避免影响你本地和现有部署。
- Alembic 已可用于记录版本、执行后续人工编写的迁移。
- 暂不启用自动生成迁移，因为导入当前模型文件会触发数据库连接和旧初始化逻辑。

已有数据库接入迁移版本管理时，先备份，再执行：

```powershell
.venv\Scripts\python.exe -m alembic stamp head
```

后续新增字段或索引时，创建迁移文件并人工确认 SQL：

```powershell
.venv\Scripts\python.exe -m alembic revision -m "add_some_column"
.venv\Scripts\python.exe -m alembic upgrade head
```

等模型定义和数据库连接初始化拆分完成后，再把 `migrations/env.py` 的 `target_metadata` 接入 `Base.metadata`，开启自动生成迁移。
