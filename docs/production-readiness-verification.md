# 生产验收：压测基线 + 备份恢复演练（2026-09-27）

`docs/project-status.md` 之前记录的两个风险项——"压力测试还未在真实服务器上形成基准
报告"、"备份命令已给出，但还需在真实部署环境做恢复演练"——在本机跑了一遍真实验证。
**这是开发机，不是生产服务器**：数字本身不能当生产容量规划的依据，但证明了
`scripts/load_test.py`/`scripts/backup.py` 这两条机制本身是对的、能跑通，真上线后
应该在实际部署的机器上重跑一遍拿真实基线（步骤完全一样，见下面命令）。

## 1. 压测基线

单进程 `uvicorn`（无 `--workers`、无 Nginx、本机 MySQL、`REDIS_URL` 为空回退内存），
`scripts/load_test.py`（[脚本本身在这次验收时补了 `--api-prefix` 参数](../scripts/load_test.py)：
直接压测后端进程没有 Nginx 在前面加 `/api` 前缀，之前脚本只支持走反代的路径）：

```bash
.venv/Scripts/python.exe -m uvicorn FasdtApi.main:app --host 127.0.0.1 --port 8124
.venv/Scripts/python.exe scripts/load_test.py --base-url http://127.0.0.1:8124 \
    --scenario health --requests 300 --concurrency 30 --api-prefix "" --json
.venv/Scripts/python.exe scripts/load_test.py --base-url http://127.0.0.1:8124 \
    --scenario auth-read --requests 200 --concurrency 20 --api-prefix "" \
    --username <test-user> --password <test-password> --json
.venv/Scripts/python.exe scripts/load_test.py --base-url http://127.0.0.1:8124 \
    --scenario mixed-read --requests 300 --concurrency 30 --api-prefix "" \
    --username <test-user> --password <test-password> --json
```

| 场景 | 请求数 | 并发 | 成功率 | RPS | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| health（公开探活） | 300 | 30 | 100% | 374.3 req/s | 69.7ms | 80.7ms | 152.3ms | 167.9ms |
| auth-read（登录+3 个鉴权读接口） | 200 | 20 | 100% | 106.8 req/s | 147.5ms | 523.1ms | 529.6ms | 535.7ms |
| mixed-read（health + 3 个鉴权读接口） | 300 | 30 | 100% | 155.6 req/s | 189.4ms | 214.0ms | 270.9ms | 299.5ms |

三个场景零失败、零 5xx。`auth-read` 的 p95/p99 明显高于 p50（523ms vs 147ms）——这是
单进程在处理登录请求时 bcrypt 校验（`run_in_threadpool` 里跑，故意慢，防暴力破解）跟
其余并发请求抢线程池的正常现象，不是 bug；生产用 `--workers 2`+ 起多进程后这个尾延迟
会明显改善，上线后应该照这条命令在真实服务器重新测一次，把这份表格换成生产数据。

## 2. 备份恢复演练

```bash
.venv/Scripts/python.exe scripts/backup.py --keep-days 14
```

产出（本次真实运行）：

- `backups/db_20260927_220422.sql`（1.6MB，`mysqldump --single-transaction --routines --triggers`）
- `backups/data_20260927_220422.tar.gz`（2.9MB，`knowledge_files`/`vector_db`/`logs`/`skills`/
  `skills_packages`/`prompt/prompts`）

恢复演练（还原到一个独立的 scratch 库，不动线上 `agent_sql`，验证完立刻删掉）：

```bash
mysql -uroot -p -e "CREATE DATABASE agent_sql_restore_drill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -p agent_sql_restore_drill < backups/db_20260927_220422.sql
# 校验：表数量、关键表行数跟原库一致
mysql -uroot -p -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='agent_sql_restore_drill';"
mysql -uroot -p -N -e "SELECT COUNT(*) FROM agent_sql_restore_drill.user;"
mysql -uroot -p -e "DROP DATABASE agent_sql_restore_drill;"
```

结果：还原耗时 1.5 秒；表数量 44/44、`user` 表 12/12 行、`agent` 表 5/5 行，跟源库完全
一致。恢复机制验证通过。真实生产库体量更大时恢复时间会更长，上线后按这份记录里的对照
步骤重新跑一次，把耗时和数据量记下来做真实基线。

## 3. 顺手发现的一个测试基建陷阱（跟本次验收无关，但排查时踩到了）

排查压测登录一直 401 时发现：`tests/_route_client.py::create_user` 注册了 `atexit`
清理钩子，如果在一个用完即退出的短生命周期脚本里调用它（不是走正常的
`unittest`/`tearDownClass` 生命周期），**进程退出的那一刻这个用户就被自动删掉了**——
不是异步/同步库看到的数据不一致，也不是应用的 bug，是这个辅助函数被用在了它没设计
给的场景（一次性脚本）。给这类"我要个持久测试账号，不想沾自动清理"的场景写了一条
更简单的方式：直接调 `models.user_dao.create_user` + `service.auth_service.hash_password`，
不经过 `_route_client`，参见本文件第 1 节的思路。这条不需要写进代码里，记在这里避免
下次再为同一个假象排查半天。
