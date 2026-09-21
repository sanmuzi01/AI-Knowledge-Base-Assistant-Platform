# Skill 预制包

`anbeime-skills-all.zip`：来自 https://github.com/anbeime/skill 的全部 Skill（75 个，1.6MB）。

## 怎么导入

用 **admin** 登录 → 后台「技能管理」→「导入能力包」→「上传文件」选这个 zip。
想让所有用户都能在「能力商店」安装，就勾选「同时公开到能力商店」。
（服务器在国内时不要用 GitHub 链接导入，上传 zip 最稳。）

## 在服务器上导入（线上库是独立的，本地导入过不会带到线上）

方式一（网页）：admin 登录 → 后台「技能管理」→「导入能力包」→「上传文件」选这个 zip → 勾选「同时公开到能力商店」。

方式二（服务器命令行，不用把 zip 下载到自己电脑）：先拉最新代码并重新构建镜像（让脚本和 zip 进容器），再执行

```bash
docker compose -f docker-compose.prod.yml build api worker
docker compose -f docker-compose.prod.yml up -d api worker
docker compose -f docker-compose.prod.yml exec api     python scripts/import_skill_pack.py skill-packs/anbeime-skills-all.zip --admin admin --public
```

`--replace` 用于重复导入 / 升级预制包（先删同名旧的）；不加时遇到同名会拒绝并列出，不会悄悄产生重复。

## 和原仓库的区别

- 名称统一换成了中文（`SKILL.md` 里的 `name`），`archify`、`ontoly-software-graph` 两个英文说明也换成了中文；正文没动。
- 重复的只留了一份，共去掉 8 个：`antinet-agentteams/skills/*` 四个（是 `skills/antinet-*` 的旧版）、
  嵌套在父 Skill 里的三个同名副本（`content-creation-publisher/article-illustrator`、`infinitetalk/infinitetalk`、
  `qiaomu-x-article-publisher/qiaomu-x-article-publisher-github`）、以及空白模板 `skills/_template`。
- 仓库根目录那个 `xiaoyue-companion` 没收（它把整个仓库 262MB 都算作自己的文件），保留了 `projects/companion-simple` 里的同一个 Skill。

## 导入后能用到什么程度

- 39 个带 Python 脚本（共 168 个）：脚本沙箱没开启时只按文字说明工作，开启方法见 `docs/deployment.md` 第 7 节。
- 8 个带 `.sh` / `.js` 脚本：这类脚本不能运行，会被跳过。
- 视频/语音生成、发布到微信或 X、浏览器自动化、网页抓取这类 Skill 依赖第三方接口、账号或联网，
  平台里没有对应能力，只能当作说明书，实际做不了事。
- `stock-analysis` 涉及个股买卖建议，对外开放前请自行评估合规风险；`contract-review` 建议在说明里加上"仅供参考，不构成法律意见"。

## 兼容性清单与后续扩展

`COMPATIBILITY.md` 是每个 Skill 的脚本兼容性清单（脚本生成，不要手改）；哪些被什么卡住、怎么解锁，见 `docs/skill-extension.md`。

## 许可证

各 Skill 的许可证以原仓库为准：`contract-review`、`law-to-markdown` 是 Apache-2.0，`archify` 是 MIT；
其余没有独立许可证文件，原仓库 README 里同时写了 CC-BY-4.0（徽章）和 MIT（正文）。公开分发前请确认。
