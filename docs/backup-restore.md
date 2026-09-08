# Backup And Restore

上线项目必须定期备份数据库和应用文件。本项目提供 PowerShell 脚本，适合 Windows 本地或 Windows 服务器运维。

## 备份内容

- MySQL 数据库：`mysql.sql`
- 知识库上传文件：`knowledge_files`
- 向量库目录：`vector_db`
- 日志目录：`logs`
- Skill 配置和包：`skills`、`skills_packages`
- Prompt 文件：`prompt/prompts`

备份输出默认在 `backups/`，该目录已加入 `.gitignore`，不要提交到 Git。

## 执行备份

先确认 Docker 服务正在运行：

```powershell
docker compose ps
```

执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1
```

成功后会生成类似：

```text
backups/agent-platform-20260830-092800.zip
```

## 恢复数据库

先解压备份包，例如：

```powershell
Expand-Archive backups/agent-platform-20260830-092800.zip -DestinationPath backups/agent-platform-20260830-092800
```

恢复数据库：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -BackupDir backups/agent-platform-20260830-092800
```

## 恢复数据库和文件

如果要同时恢复知识库文件、向量库、Skill 和 Prompt：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -BackupDir backups/agent-platform-20260830-092800 -RestoreFiles
```

`-RestoreFiles` 会覆盖当前项目中的对应目录，执行前必须确认备份版本正确。

## 上线建议

- 每次发布前做一次手动备份。
- 每天至少做一次自动备份。
- 备份包要放到服务器以外的位置，例如对象存储或另一台机器。
- 定期做恢复演练，只备份不验证恢复等于没有备份。
- `.env` 不会进入备份包，生产密钥要单独用安全方式保存。
