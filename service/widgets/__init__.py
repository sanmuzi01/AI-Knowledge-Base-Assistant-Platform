"""自然语言驱动的自定义工作台组件平台。

分层：
- schema.py       所有白名单枚举 + 组件配置结构 + 面向普通用户的中文描述（单一事实来源）
- context.py      WidgetRunContext：运行上下文（user_id / widget_id / now / db / request_id）
- registry.py     通用注册表工具
- connectors/     数据源连接器注册表，统一接口 fetch(ctx, config) -> raw_data
- processors.py   处理器注册表，统一接口 process(ctx, raw_data, config) -> processed_data
- validator.py    把（LLM 产出的）原始 JSON 校验/归一成白名单内的合法配置
- designer.py     /design：调用用户自己的模型，产出组件草稿
- runner.py       run_widget(widget_id)：唯一运行入口，手动运行与未来 Worker 调度都走这里
- scheduler.py    到点组件的调度入口（P1 预留 + 已实现 due 查询与批量运行）
"""
