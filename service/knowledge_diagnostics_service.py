import os
from typing import Dict, List

from sqlalchemy import func

from models.init_db import Agent, BackgroundTask, Knowledge, LLMConfig
from service.llm.model_catalog import model_type
from service.web_crawler_service import CrawlerError, validate_crawl_url


def _status_counts(db, model, user_id: int, agent_id: int) -> Dict[str, int]:
    rows = (
        db.query(model.status, func.count(model.id))
        .filter(model.user_id == user_id, model.agent_id == agent_id)
        .group_by(model.status)
        .all()
    )
    return {status or "unknown": int(count or 0) for status, count in rows}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _crawler_settings() -> Dict:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    return {
        "app_env": app_env,
        "browser_fallback": _env_bool("CRAWLER_BROWSER_FALLBACK", False),
        "allow_private_network": _env_bool("CRAWLER_ALLOW_PRIVATE_NETWORK", False),
        "allow_private_dns": _env_bool("CRAWLER_ALLOW_PRIVATE_DNS", app_env not in {"production", "prod"}),
        "timeout_seconds": float(os.getenv("CRAWLER_TIMEOUT_SECONDS", "10")),
        "max_bytes": int(os.getenv("CRAWLER_MAX_BYTES", str(2 * 1024 * 1024))),
        "min_text_length": int(os.getenv("CRAWLER_MIN_TEXT_LENGTH", "50")),
        "user_agent": os.getenv("CRAWLER_USER_AGENT", "AgentPlatformCrawler/1.0"),
    }


def build_knowledge_recommendations(
        *,
        has_embedding_model: bool,
        done_docs: int,
        failed_docs: int,
        failed_tasks: int,
        working_docs: int,
        queued_tasks: int,
        browser_fallback: bool,
) -> List[Dict]:
    recommendations = []
    if not has_embedding_model:
        recommendations.append({
            "key": "embedding-model",
            "level": "danger",
            "title": "先连接向量模型",
            "description": "没有向量模型时，文档无法入库，检索也不会返回片段。",
            "action_text": "去配置",
            "action_path": "/llm-configs",
        })
    if done_docs == 0:
        recommendations.append({
            "key": "no-searchable-doc",
            "level": "warn",
            "title": "还没有可检索资料",
            "description": "上传文件或抓取网页后，需要等待后台任务完成，状态变成已完成才可检索。",
            "action_text": "添加资料",
            "action_path": "",
        })
    if failed_docs or failed_tasks:
        recommendations.append({
            "key": "failed-index",
            "level": "warn",
            "title": "处理失败任务",
            "description": f"当前有 {failed_docs + failed_tasks} 个失败项，建议查看错误原因后重建或重试。",
            "action_text": "查看失败",
            "action_path": "",
        })
    if working_docs or queued_tasks:
        recommendations.append({
            "key": "wait-worker",
            "level": "info",
            "title": "等待后台 Worker",
            "description": "资料正在排队或处理中。生产环境建议独立启动 Worker，避免任务一直停留在排队中。",
            "action_text": "看进度",
            "action_path": "/tasks",
        })
    if not browser_fallback:
        recommendations.append({
            "key": "browser-fallback",
            "level": "info",
            "title": "动态网页可启用浏览器兜底",
            "description": "强依赖 JS 渲染的网站可能抓不到正文，可在部署环境开启 CRAWLER_BROWSER_FALLBACK。",
            "action_text": "了解原因",
            "action_path": "",
        })
    return recommendations[:5]


def get_knowledge_diagnostics(db, user_id: int, agent_id: int) -> Dict:
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.user_id == user_id).first()
    configured_models = [
        config.model_name
        for config in db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.is_active == 1).all()
    ]
    embedding_models = [name for name in configured_models if model_type(name) == "embedding" or name.lower() == "glm-4"]
    doc_status = _status_counts(db, Knowledge, user_id, agent_id)
    task_status = _status_counts(db, BackgroundTask, user_id, agent_id)
    settings = _crawler_settings()

    done_docs = doc_status.get("done", 0)
    failed_docs = doc_status.get("failed", 0)
    working_docs = doc_status.get("pending", 0) + doc_status.get("processing", 0)
    queued_tasks = task_status.get("queued", 0) + task_status.get("running", 0)
    failed_tasks = task_status.get("failed", 0)
    has_embedding_model = bool(embedding_models)
    score = 100
    if not has_embedding_model:
        score -= 40
    if done_docs == 0:
        score -= 22
    if failed_docs or failed_tasks:
        score -= min(24, (failed_docs + failed_tasks) * 8)
    if working_docs or queued_tasks:
        score -= 6

    return {
        "agent": {
            "id": agent.id if agent else agent_id,
            "name": agent.name if agent else "",
            "rag_enabled": agent.rag_enabled if agent else 0,
        },
        "score": max(0, min(100, score)),
        "embedding": {
            "ready": has_embedding_model,
            "models": embedding_models,
        },
        "documents": {
            "status": doc_status,
            "searchable_count": done_docs,
            "working_count": working_docs,
            "failed_count": failed_docs,
        },
        "tasks": {
            "status": task_status,
            "active_count": queued_tasks,
            "failed_count": failed_tasks,
        },
        "crawler": settings,
        "recommendations": build_knowledge_recommendations(
            has_embedding_model=has_embedding_model,
            done_docs=done_docs,
            failed_docs=failed_docs,
            failed_tasks=failed_tasks,
            working_docs=working_docs,
            queued_tasks=queued_tasks,
            browser_fallback=settings["browser_fallback"],
        ),
    }


def check_crawl_urls(urls: List[str]) -> Dict:
    results = []
    for raw_url in urls[:10]:
        url = (raw_url or "").strip()
        if not url:
            continue
        try:
            normalized_url = validate_crawl_url(url)
            results.append({
                "url": url,
                "normalized_url": normalized_url,
                "ok": True,
                "error": "",
            })
        except CrawlerError as exc:
            results.append({
                "url": url,
                "normalized_url": "",
                "ok": False,
                "error": str(exc),
            })
    return {
        "count": len(results),
        "ok_count": len([item for item in results if item["ok"]]),
        "failed_count": len([item for item in results if not item["ok"]]),
        "items": results,
    }
