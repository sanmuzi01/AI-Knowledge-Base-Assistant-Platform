# Testing

项目当前使用 Python `unittest` 做基础单元测试，不依赖真实 MySQL、Redis、短信服务或大模型。

## 运行单元测试

```powershell
npm run test:unit
```

当前覆盖：

- TTL 缓存过期和深拷贝保护。
- 注册短信验证码发送、校验、一次性消费和手机号格式拦截。
- HTTP 外部调用重试和熔断。
- 模型厂商识别和默认 API URL 自动适配。
- 生产环境配置校验，防止占位密钥、无 Redis、短信误配置上线。

## 上线前建议测试顺序

```powershell
.venv\Scripts\python.exe -m compileall FasdtApi service models utils scripts tests
npm run test:unit
npm run frontend:build
npm run load:test -- --base-url http://127.0.0.1 --scenario health --requests 200 --concurrency 20
```

## CI 质量门禁

每次 push / PR，GitHub Actions（`.github/workflows/ci.yml`）依次跑：编译检查 → ruff → 依赖漏洞扫描 →
单元测试 + 覆盖率 → （前端）依赖漏洞扫描 → 类型检查 + 构建。任意一步失败，PR 不能合。

### 覆盖率

```powershell
npm run test:coverage
```

等价于 `coverage run -m unittest discover -s tests` + `coverage report --fail-under=64` + `coverage xml`。
配置在 `pyproject.toml` 的 `[tool.coverage.*]`：只统计 `FasdtApi/service/models/utils`（业务代码），
排除 `migrations/` 和 `utils/log_to_csv.py`（没有任何路由/服务调用的一次性运维脚本，放业务代码目录纯属历史遗留）。

当前真实基线约 **64.6%**，门槛先设 **64%**（如实反映现状，没有靠扩大排除范围硬凑到 65%）。按下面顺序调高：

1. 新增功能必须带测试，不能让覆盖率因为新代码被拉低。
2. 挑覆盖率低但**活跃使用**的模块（`coverage report` 按 Miss 列排序能看出来，比如目前的
   `service/agent_service.py`、`FasdtApi/knowledge.py`）逐个补测试，覆盖率过 65% 后把
   `--fail-under` 提到 65，之后同样的方法继续提到 75。
3. 不要为了凑数字给不常用的代码加空测试，也不要为了让数字好看把活跃代码加进 `omit`。

### Lint（ruff）

```powershell
npm run lint:py
```

`pyproject.toml` 里 `select = ["E9", "F"]`：只挡语法错误和 pyflakes（未使用的导入/变量、用到没定义的名字等）——
大概率是 bug，不是风格问题。**没有**开 ruff 默认更大的规则集（pyupgrade / bugbear / bandit 等），
现状代码库全量跑一遍有约 2900 条，绝大多数是"能跑但不够新"的风格建议，不是缺陷，硬开只会把 CI 变成没人看的噪音。
想扩大检查范围：先加一类规则跑一遍看有多少违规，评估要不要一次清干净，再加进 `select`。

### 依赖漏洞扫描

```powershell
npm run audit:py    # 后端，pip-audit
npm run audit:npm   # 前端，npm audit（只挡 high/critical）
```

`pip-audit` 的输出没有统一的严重度字段（不像 npm audit 有 severity），所以后端这边按"能不能修"分类，
不是按"严重度"分类：**有修复版本却没升级** → 阻断 CI，逼着升级；**上游还没出修复版本** → 记录在
CI 配置里、写清楚原因，不阻断（阻断了也没用，只会让 CI 一直红）。当前免检名单（`.github/workflows/ci.yml`
的 `--ignore-vuln` 参数，定期复查，上游出新版本就把对应这条删掉）：

| 依赖 | 漏洞 | 为什么先不阻断 |
|---|---|---|
| `asyncmy` 0.2.10 | PYSEC-2026-286，SQL 注入（"通过精心构造的 dict key"） | 上游到最新版 0.2.11 仍未修复；本项目原生 SQL 只在极少数地方用固定参数名的 `text()`，不会把用户输入当 dict key 传给驱动，可利用面很小 |
| `chromadb` 1.5.9 | PYSEC-2026-311/3813/3814/3815，未授权访问、代码注入、跨租户越权 | 1.5.9 已是最新版，上游未修复；`docker-compose.prod.yml` 里 `chroma` 服务没有 `ports:` 映射，只有 api/worker 能从容器内网访问，不对公网暴露 |
| `ecdsa` 0.19.2 | PYSEC-2026-1325，Minerva 时序攻击（侧信道泄露私钥） | `python-jose` 的间接依赖；项目 JWT 固定用 `HS256`（对称算法），根本不会走到 `ecdsa` 的签名代码路径；上游明确表示侧信道防护不在其修复范围内 |

前端目前有 1 条 moderate（`echarts` XSS，`GHSA-fgmj-fm8m-jvvx`，修复需升到 6.x 大版本，有破坏性变更，
未安排）；`--audit-level=high` 不会拦它，`npm audit` 手动跑能看到。

发布前想看完整报告（含以上免检项，不只是阻断的那部分）：
```powershell
npm run audit:py
```
不带 `--ignore-vuln` 直接跑，看到的就是全部已知漏洞。

## 路由级测试的数据清理

`tests/_route_client.py` 建的 `rt_*` 用户是**真实落库**的。清理机制：

- `cleanup()`（`tearDownClass` 调）—— 按本进程建的 id 删，级联清 agent / 知识库 / 空间 /
  组件 / 会话 / operation_log 等；**每条 DELETE 独立提交**，某表撞 FK 不会连累其它（历史上
  测试用户越积越多就是因为一条失败回滚了整轮）。
- 进程退出兜底：`atexit` 里再跑一次 `cleanup()`，`setUpClass` 崩了 / Ctrl+C 也不会漏。
- 手动清历史残留：`.venv\Scripts\python.exe scripts\purge_test_users.py --dry-run`（统计）/
  `--yes`（删掉库里**所有** `rt_%` 用户，真实用户不动）。

## 后续应补充

- 使用测试数据库覆盖注册、登录、权限隔离和管理员接口。
- 使用临时文件目录覆盖知识库上传、入库任务和删除。
- 使用 mock LLM/Embedding 服务覆盖聊天、RAG 检索和外部服务失败降级。
- 在 CI 中自动执行编译、单元测试和前端构建。
