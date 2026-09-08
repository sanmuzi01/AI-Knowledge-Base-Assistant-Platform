# 数据库迁移说明

项目已经加入 Alembic 迁移骨架，用于让后续字段、索引、表结构调整变成可审计、可回滚、可发布前检查的流程。

## 当前状态

当前仍是兼容过渡期：

- `models/init_db.py` 继续保留 `create_all` 和幂等补字段逻辑，但已收敛进 `bootstrap_database()` 函数，
  不再在模块导入时执行。运行时由 FastAPI lifespan（`FasdtApi/main.py`）和后台 Worker（`service/background_worker.py`）
  启动时各调用一次；离线执行用 `python -m models.init_db`。
- 用 `DB_AUTO_BOOTSTRAP=0` 可关闭自动建表/迁移（改由 Alembic 完全接管表结构的部署场景）。
- `migrations/versions/20260830_0001_baseline.py` 是基线版本，用来把已有数据库纳入 Alembic 版本管理。
- 导入模型不再连接数据库，因此可以逐步开启 Alembic 自动生成迁移（把 `target_metadata` 接入 `Base.metadata`）。

## 已有数据库接入

上线或测试环境已有表时，先备份：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1
```

确认当前表结构已经由应用启动补齐后，执行：

```powershell
npm run db:stamp
npm run db:current
```

这一步只记录“当前库已经处于基线版本”，不会修改表结构。

## 后续新增迁移

新增字段、索引或表时：

```powershell
.venv\Scripts\python.exe -m alembic revision -m "add_xxx"
```

然后在生成的迁移文件中手写 `upgrade()` 和 `downgrade()`，检查确认后执行：

```powershell
npm run db:migrate
```

## 下一步优化

后续建议把 `models/init_db.py` 拆成三层：

- 纯模型定义：只声明 `Base` 和 ORM 类。
- 数据库连接工厂：只创建 `engine` 和 `SessionLocal`。
- 启动初始化：只在应用启动命令中显式执行。

拆分完成后，Alembic 的 `target_metadata` 可以接入 `Base.metadata`，再开启自动生成迁移。
