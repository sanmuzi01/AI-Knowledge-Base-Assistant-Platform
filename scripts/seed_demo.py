"""一键塞一份可玩的演示数据：demo 用户 + 示例助手 + 一份已入库的知识库文档。

用本地 BGE 向量模型（`sentence-transformers`，无需任何 API Key），所以
「上传 → 入库 → 检索 → 引用」整条链路开箱即跑；只有「聊天」还需要你自己在
【模型连接】里填一个聊天模型的 Key。

用法（项目根目录）：
    .venv/Scripts/python.exe scripts/seed_demo.py
    .venv/Scripts/python.exe scripts/seed_demo.py --reset   # 先清掉旧的 demo 数据再建
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:  # Windows 控制台默认 GBK，输出中文/符号会炸
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from service.config_validation import is_production  # noqa: E402

if is_production():
    # 放在所有会连数据库的 import 之前：即使远端就是生产库也不会有任何写操作发生。
    print("拒绝执行：APP_ENV=production，这个脚本会建一个密码是 demo12345 的账号，不能对生产库跑。")
    sys.exit(1)

from sqlalchemy import text  # noqa: E402
from models.init_db import SessionLocal, bootstrap_database  # noqa: E402

DEMO_USER = "demo"
DEMO_PASS = "demo12345"
EMB_MODEL = "BAAI/bge-small-zh-v1.5"   # provider=local，不需要 Key

SAMPLE_NAME = "示例-云盘产品说明.md"
SAMPLE_DOC = """# 云盘产品说明（演示文档）

## 套餐与容量
- 免费版：15 GB 存储空间，单文件上传上限 2 GB。
- 专业版：2 TB 存储空间，单文件上传上限 50 GB，每月 39 元。
- 团队版：按人数计费，每个成员 100 元/月，含 5 TB 共享空间与管理后台。

## 文件恢复
删除的文件进入回收站，免费版保留 10 天，专业版和团队版保留 30 天。
回收站内可一键还原；超过保留期后文件不可恢复。

## 分享与权限
分享链接可设置「仅查看」或「可编辑」，并可加访问密码和有效期（1 天 / 7 天 / 30 天 / 永久）。
团队版支持按文件夹设置成员角色：所有者 / 管理员 / 编辑者 / 只读。

## 同步客户端
Windows / macOS / Linux 均有桌面客户端，支持选择性同步（只同步指定文件夹）。
移动端支持照片自动备份，可设置仅在 Wi-Fi 下上传。

## 常见问题
- 上传失败：优先检查单文件是否超过套餐上限，其次检查网络。
- 找回误删文件：到回收站还原，注意保留期限制。
- 退订专业版：到「账户 - 订阅」关闭自动续费，当前周期到期后降级为免费版，
  超出 15 GB 的文件将变为只读直到容量释放。
"""


def _wipe_demo(db):
    row = db.execute(text("SELECT id FROM `user` WHERE name=:n"), {"n": DEMO_USER}).first()
    if not row:
        return
    uid = row[0]
    # 复用测试清理里的那套级联删除
    from tests._route_client import _purge_users
    _purge_users(f"id = {uid}")
    print(f"已清掉旧的 demo 数据（user_id={uid}）")


def main() -> int:
    reset = "--reset" in sys.argv
    bootstrap_database()

    db = SessionLocal()
    try:
        if reset:
            _wipe_demo(db)
            db.commit()  # 让本会话看到 _purge_users（独立会话）刚提交的删除

        exists = db.execute(text("SELECT id FROM `user` WHERE name=:n"), {"n": DEMO_USER}).first()
        if exists:
            print(f"demo 用户已存在（id={exists[0]}）。要重建加 --reset。")
            _print_hint()
            return 0

        from models.user_dao import create_user
        from models.agent_dao import create_agent
        from models.llm_config_dao import create_config
        from service.auth_service import hash_password
        from utils.crypto import encrypt
        from service.rag import rag_service

        user = create_user(db, name=DEMO_USER, password=hash_password(DEMO_PASS), age=30)
        print(f"- 用户 {DEMO_USER} / {DEMO_PASS}（id={user.id}）")

        create_config(db, user.id, EMB_MODEL, api_key=encrypt("local"), api_url=None)
        db.commit()
        print(f"- 资料读取能力：{EMB_MODEL}（本地模型，无需 Key）")

        agent = create_agent(db, name="示例助手", user_id=user.id, model_name="glm-4",
                             rag_enabled=1, memory_enabled=0)
        db.commit()
        print(f"- 助手「示例助手」（id={agent.id}），已开启知识库")

        print("... 正在入库示例文档（本地向量化，首次会加载模型，稍等）")
        res = rag_service.upload_and_index(
            db, user.id, agent.id, SAMPLE_NAME, SAMPLE_DOC.encode("utf-8"), "md",
        )
        db.commit()
        print(f"- 文档已入库：{SAMPLE_NAME}，切成 {res.get('chunk_count')} 块")

        # 顺手验证检索能跑
        from service.rag.search_entry import search_scoped
        hits = search_scoped(user.id, agent.id, "回收站文件能保留多久", top_k=3)
        print(f"- 检索自检：问「回收站保留多久」命中 {len(hits)} 条")

    finally:
        db.close()

    _print_hint()
    return 0


def _print_hint():
    print()
    print("-" * 56)
    print(f"  登录：{DEMO_USER} / {DEMO_PASS}    →  http://localhost:5173")
    print("  可以直接玩：")
    print("   · 知识库 → 看「示例-云盘产品说明」已入库，点「片段」看切块")
    print("   · 知识库中心 → 调试台：问「专业版多少钱」看检索全过程")
    print("   · 聊天：需先在【模型连接】填一个聊天模型 Key（智谱/DeepSeek/…）")
    print("-" * 56)


if __name__ == "__main__":
    raise SystemExit(main())
