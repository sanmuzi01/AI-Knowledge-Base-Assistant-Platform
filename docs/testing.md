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

## 后续应补充

- 使用测试数据库覆盖注册、登录、权限隔离和管理员接口。
- 使用临时文件目录覆盖知识库上传、入库任务和删除。
- 使用 mock LLM/Embedding 服务覆盖聊天、RAG 检索和外部服务失败降级。
- 在 CI 中自动执行编译、单元测试和前端构建。
