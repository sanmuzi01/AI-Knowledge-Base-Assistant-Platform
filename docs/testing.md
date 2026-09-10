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
