# 存档：squash 之前的迁移文件

这 8 个文件（`20260830_0001` ～ `20260923_0008`）**不再参与** `alembic upgrade`——它们
已经不在 `migrations/versions/` 目录里，Alembic 看不到它们。

留着只是存档，方便查"某个字段/表是什么时候、为什么加的"这类历史。真正管用的是
`migrations/versions/20260924_0001_trusted_baseline.py`，它是对着一个全新空库用
`alembic revision --autogenerate` 重新生成的，覆盖了这 8 个文件曾经想做的所有事——
包括它们从未真正做到的部分：这 8 个文件写下来之后从没有被 `alembic upgrade` 真正
执行过一次（`alembic_version` 表在任何环境里都不存在），当前数据库的实际结构一直是
`models/init_db.py` 的 `Base.metadata.create_all()` + 手写幂等 `ALTER TABLE`
拼出来的。详情见 [docs/db-migration-plan.md](../../docs/db-migration-plan.md)。

为什么可以直接"重新生成基线 + 删掉旧链"而不是给旧链打补丁：因为从来没有任何环境
（本地、CI、生产）真的用 Alembic 走过这条链——`alembic_version` 表从未被写过，
所以这不是"改写正在依赖的历史"，是"把从来没生效过的记录换成真的能用的"。
