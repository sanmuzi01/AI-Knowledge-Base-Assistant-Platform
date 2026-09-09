"""一次性存量迁移：把 Agent 私有知识库升级到「默认知识库空间」。

对每个还没有 space_id 的 knowledge 行：
  - 按 (user_id, agent_id) 找/建一个默认空间（legacy_agent_id=agent_id, vector_migrated=0）
  - 回填 knowledge.space_id / source_type
  - 回填每个空间的 doc_count / chunk_count

只加不删：knowledge.agent_id 保留；向量库不动（检索阶段3 会对 legacy 空间做双读）。
幂等：重复运行只处理新出现的未迁移行。

用法：
  python -m scripts.migrate_agent_kb_to_space            # dry-run，只打印计划
  python -m scripts.migrate_agent_kb_to_space --apply    # 实际写库
"""

import sys

from models.init_db import Agent, Knowledge, SessionLocal, bootstrap_database
from service.knowledge_space.space_service import ensure_default_space_for_agent, recount_space
from utils.timeutil import utcnow


def run(apply: bool) -> dict:
    db = SessionLocal()
    try:
        pending = (
            db.query(Knowledge)
            .filter(Knowledge.space_id.is_(None))
            .order_by(Knowledge.user_id, Knowledge.agent_id, Knowledge.id)
            .all()
        )
        if not pending:
            print("没有待迁移的知识库文档。")
            return {"docs": 0, "spaces": 0}

        agent_name = {a.id: a.name for a in db.query(Agent.id, Agent.name).all()}
        space_cache: dict = {}   # (user_id, agent_id) -> space_id
        touched_spaces = set()
        migrated = 0

        for k in pending:
            key = (k.user_id, k.agent_id)
            if key not in space_cache:
                if apply:
                    sid = ensure_default_space_for_agent(
                        db, k.user_id, k.agent_id, agent_name.get(k.agent_id, "")
                    )
                else:
                    sid = f"<新建/复用: user={k.user_id} agent={k.agent_id}>"
                space_cache[key] = sid
                print(f"空间 {key} -> {sid}")
            sid = space_cache[key]
            if apply:
                k.space_id = sid
                if not k.source_type:
                    k.source_type = "upload"
                k.updated_at = utcnow()
                touched_spaces.add(sid)
            migrated += 1

        if apply:
            db.commit()
            for sid in touched_spaces:
                recount_space(db, sid)
            print(f"\n已迁移 {migrated} 个文档，涉及 {len(touched_spaces)} 个空间。")
        else:
            print(f"\n[dry-run] 将迁移 {migrated} 个文档，涉及 {len(space_cache)} 个空间。加 --apply 执行。")
        return {"docs": migrated, "spaces": len(space_cache)}
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap_database(seed_admin=False)
    run(apply="--apply" in sys.argv)
