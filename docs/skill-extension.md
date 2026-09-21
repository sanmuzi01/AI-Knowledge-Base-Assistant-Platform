# Skill 与脚本沙箱：现状、保留的内容、后续扩展

给以后接手的人（包括未来的自己）：这一块做到哪了、为什么这样做、想继续扩展该从哪里下手。
部署与开启沙箱的步骤在 [deployment.md](deployment.md) 第 7 节，这里不重复。

## 1. 现状一页纸

- **导入**：管理员在后台「技能管理」导入官方 Skill / GitHub 仓库 zip / 本平台能力包。`SKILL.md` 正文变成助手的提示词；
  参考文档在字数预算内并入提示词；**Python 脚本**连同 Skill 的其他文件存成「脚本包」（`skills_packages/imported/<id>/bundle`）。
- **执行**：脚本**不在主服务里跑**，由独立的沙箱容器执行（无外网、无密钥、只读根、CPU/内存/进程数上限）。
  助手通过 `run_skill_script` 工具调用；用户在聊天里上传附件（脚本从 `inputs/` 读），脚本写到 `outputs/` 的文件变成下载链接。
- **信任模型**：只有管理员能导入带脚本的 Skill、能公开到「能力商店」（标「官方」）；普通用户只能安装、绑定、上传输入文件、使用。
  `SANDBOX_ALLOW_USER_SCRIPTS=false`，**不开放用户自带脚本**。
- **可用性标签**：导入时对每个 `.py` 静态检查（缺依赖 / 联网 / 调系统命令），卡片上标「脚本可运行 / 部分脚本可运行 / 脚本暂不支持 /
  脚本需管理员启用沙箱」；助手只被告知通过检查的脚本。
- **默认关闭**：`SANDBOX_ENABLED=false`。没开时脚本只保存不运行，助手按文字说明工作。

## 2. 保留下来的内容

这次有意**不删、不藏**目前跑不了的 Skill，留作以后扩展的素材：

| 保留的东西 | 位置 | 说明 |
|---|---|---|
| 全部 75 个 Skill 的预制包 | `skill-packs/anbeime-skills-all.zip` | 来自 `anbeime/skill`，名称已中文化；去掉了 8 个重复/空白模板（见 `skill-packs/README.md`） |
| 兼容性清单 | `skill-packs/COMPATIBILITY.md` | 每个 Skill 的状态、缺什么依赖、被什么类别卡住。由脚本生成，见下 |
| 清单生成脚本 | `scripts/skill_compat_report.py` | 只读源码，不执行脚本；加了依赖后重新生成，前后差异 = 多解锁了哪些 Skill |
| 「重新检查脚本」按钮 | 后台技能管理页 → `POST /skill/admin/reanalyze` | 沙箱依赖变了以后刷新已导入 Skill 的标签，不用重新导入 |
| 不能运行的脚本本身 | 预制 zip 里原样保留 | `.sh` / `.js` 等非 Python 脚本在 zip 里都在；导入平台后，只有同时带 `.py` 的 Skill 才会存成脚本包（这时它们随包保存但不运行）。以后加了对应运行时，重新导入即可启用 |

商店里不隐藏这些 Skill，靠卡片上的红/黄标签在**安装前**告诉用户能不能用。如果以后想收起来：管理员把它设为不公开即可（数据都还在）。

重新生成清单：

```bash
.venv\Scripts\python.exe scripts/skill_compat_report.py skill-packs/anbeime-skills-all.zip -o skill-packs/COMPATIBILITY.md
```

## 3. 解锁被卡住的 Skill：按类别要做什么

`COMPATIBILITY.md` 末尾按类别列了卡点。每一类的解法不同，难度和风险也不同：

| 类别 | 典型库 | 要做什么 | 难度 / 主要风险 |
|---|---|---|---|
| 需要联网 | `requests`、`edge_tts`、`langchain_openai` | 受控出网：给沙箱加一个出站代理容器，只放行**每个 Skill 声明过的域名**，每次请求进审计日志；Skill 配置里已有 `permissions.network` 字段但目前**没有强制执行** | 高。数据外泄、SSRF、费用失控。不要做成"整体放开外网" |
| 平台专属 SDK | `coze_workload_identity` | 写适配层（同名模块，把调用转到你自己的模型/服务），或者直接改写这些 Skill | 中。要逐个看 Skill 实际用了 SDK 的哪部分 |
| 深度学习 / 模型权重 | `torch`、`transformers`、`kokoro`、`librosa` | **单独的 GPU / 大内存沙箱后端**（实现 `service/sandbox.py::SandboxBackend` 的另一个类，比如云函数），模型权重烘进镜像或只读挂载。不要塞进现有 1GB 沙箱 | 高。成本、镜像体积、冷启动 |
| 浏览器自动化 | `patchright`、`playwright` | 独立的无头浏览器沙箱 + 网络白名单 + 会话隔离 | 高。攻击面大 |
| 仓库内部模块缺失 | `runtime`、`src` | Skill 本身不完整：从原仓库补齐缺的文件重新打包，或者不收 | 低，但要人工看 |
| 系统组件 / 常驻服务 | `flask`、`schedule`、`pyttsx3`、`pdf2image` | 大多在沙箱里没有意义（起服务、定时任务、系统语音）。`pdf2image` 需要 poppler，可改用已装的 `pypdfium2` | 低，多数建议放弃 |
| 非 Python 脚本 | `.sh`、`.js` | 多运行时 runner：目前 `sandbox/runner.py` 只接受 `.py`；加 Node 镜像变体并让 runner 按扩展名选解释器 | 中 |
| 已评估、暂未安装 | `moviepy` | 官方 Skill 用的 1.0.3 与新版 Pillow（`Image.ANTIALIAS` 已删除）和 NumPy 2 有已知不兼容。在能实机验证前不装；可能需要 `sitecustomize` 补丁 | 中，先在容器里实测 |

## 4. 日常：往沙箱加 Python 库

原则：**离线可用、纯 CPU、不需要模型权重、不需要网络**。步骤：

1. 改 `sandbox/requirements.txt`（尽量写精确版本）。
2. 改 `service/skills_core/script_report.py::PACKAGE_MODULES`：键是 pip 包名（小写），值是它对应的 `import` 名，
   连同它带进来、脚本可能直接 import 的依赖模块。
3. `python -m unittest tests.test_skill_script_report`：会校验 requirements 和 `PACKAGE_MODULES` 两边一致，对不上直接失败。
4. 重建沙箱镜像并重启沙箱。
5. 后台「技能管理」→「重新检查脚本」。
6. 重新生成 `skill-packs/COMPATIBILITY.md` 并提交。

## 5. 开放用户自带脚本之前必须补齐的

当前**不满足**这些条件，所以不开放。逐项现状：

| 项 | 现状 | 缺口 |
|---|---|---|
| 文件隔离 | 每次运行独立临时目录；容器只读根、无外网；输入只能是本人附件 | 全站共用一个沙箱容器，没有按用户/每次运行新建容器 |
| 依赖管理 | 全站一份固定依赖 | 用户无法自带依赖；部分版本还是 `>=` 未锁死 |
| 审计 | `sandbox_audit` 日志：用户、助手、Skill、脚本、退出码、耗时 | 不留脚本内容/哈希，没有异常告警 |
| 配额 | 次数限频、附件容量 | 没有 CPU 秒 / 内存用量计量，没有计费 |
| 审核 | 管理员导入即信任；只有管理员能上架 | 没有变更审核、版本、回滚、下架原因 |
| 对抗恶意脚本 | 容器隔离 + rlimit + 超时 | 没有 gVisor / seccomp 等更强隔离，没做过容器逃逸评估；用户脚本还需要静态扫描（危险调用、混淆） |

## 6. 验收清单（部署后逐条打勾）

静态检查不等于能跑，开启沙箱后必须实测。

- [ ] 沙箱容器启动且健康（`docker compose ... ps`）
- [ ] 网络隔离两条命令都**失败**（见 deployment.md 第 7 节）。任何一条成功 = 立刻关沙箱
- [ ] 代表性 Skill 各跑一遍「上传文件 → 助手运行脚本 → 下载结果」：
  合同审阅（18 个脚本全标可运行）、PPTX 生成、PDF 处理 Pro、历史人物访谈脚本、音视频处理
- [ ] `logs/sandbox_audit_*.log` 里能看到这些运行记录
- [ ] 连续触发超过限频（默认 60 秒 10 次）会收到"脚本运行太频繁"
- [ ] 附件超额（100MB / 50 个）会明确提示，不是悄悄失败
- [ ] 卡片上标「可运行」的实测都能跑；不一致的记下来，修 `script_report` 的规则或加依赖
- [ ] 视频类脚本确认是否被 30 秒 / 1GB 上限终止（"依赖齐了"不代表"跑得完"）
- [ ] 服务器内存够（沙箱上限 1GB；2 核 4G 的机器建议降到 512MB）

实测结果建议记在这里，下次扩展时对照：

| 日期 | Skill | 脚本 | 结果 | 备注 |
|---|---|---|---|---|
| | | | | |

## 7. 代码地图

| 文件 | 作用 |
|---|---|
| `sandbox/runner.py`、`Dockerfile`、`requirements.txt` | 沙箱容器：写入文件 → 跑脚本 → 带回 stdout 和新文件；令牌校验、并发上限、rlimit、超时 |
| `service/sandbox.py` | `SandboxBackend` 抽象 + `RunnerBackend`（HTTP 调 runner）。**换云沙箱 / GPU 后端从这里接** |
| `service/tools/skill_script.py` | `run_skill_script` 工具：打包脚本包和附件 → 调沙箱 → 存产出文件；限频、审计 |
| `service/skills_core/package_import.py` | 导入：格式识别、去重、脚本包落盘、参考文档预算、`allow_scripts` 权限 |
| `service/skills_core/script_report.py` | 静态兼容性检查、`PACKAGE_MODULES`、`reanalyze_config` |
| `service/skills_core/binding.py` | 绑定到助手时按沙箱状态注入脚本说明和工具，只暴露通过检查的脚本 |
| `service/skills_core/validation.py` | 生成卡片标签所需的 `script_status` 等字段 |
| `service/skills/loader.py` | 配置校验：`scripts_root` / `resource_root` 只能指向平台管理的目录（防上传 yml 指向 `.env`） |
| `service/skills_core/github_import.py`、`translate.py` | GitHub 链接导入（固定走 codeload）、名称说明翻译成中文 |
| `service/attachment_service.py`、`FasdtApi/attachment_route.py` | 附件与产出文件：按用户隔离、保留期、容量上限 |
| `FasdtApi/skill_route.py` | 导入策略（脚本/公开仅管理员）、`/skill/admin/reanalyze` |
| `frontend/src/views/SkillList.vue`、`Chat.vue` | 卡片标签、导入窗口、附件上传与下载 |
| `tests/test_skill_sandbox.py`、`test_skill_script_report.py`、`test_skill_script_policy.py`、`test_skill_package_import.py`、`test_skill_translate.py` | 覆盖以上链路 |

## 8. 决策记录（为什么这样做）

- **自建沙箱容器 + 可替换接口**，而不是直接用云沙箱：起步成本最低、不依赖外部服务；把接口抽出来，量大或需要 GPU 时换后端只改一处。
- **脚本默认关闭、只有管理员能带**：这相当于让服务器执行第三方代码。信任放在"管理员审核过的 Skill"上，而不是"任何用户上传的脚本"。
- **不装 `requests` 等联网库**：沙箱没有外网，装上只会让脚本跑到一半才报错，比提前标「暂不支持」更糟。
- **不装 `torch` 等**：要下载模型权重（同样需要网络），镜像会涨到几个 GB，1GB 内存也带不动。
- **不装 `moviepy`**：兼容性没法在当时实机验证，宁可标「暂不支持」也不标一个跑不通的「可运行」。
- **用静态检查而不是运行时探测**：不用执行陌生脚本就能给出标签。代价是不准——动态 import、运行时拼出来的命令查不出来，
  所以有第 6 节的实测验收。
- **保留跑不了的 Skill**：它们是以后扩展的素材，也是最直观的"还差什么"清单；用标签透明告知，而不是悄悄删掉。
- **`scripts_root` 只能指向 `skills_packages`**：早期版本允许上传的 yml 声明任意目录，会让沙箱把项目根目录（含 `.env`）打包读出来，已修并有测试。
