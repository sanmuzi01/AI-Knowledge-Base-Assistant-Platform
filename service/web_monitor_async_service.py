"""网页监控服务。"""

import hashlib
from datetime import datetime
from typing import Dict

from sqlalchemy import select

from models import web_monitor_async_dao as dao
from models.init_db import Agent
from service.web_crawler_async_service import async_crawl_url_to_markdown, async_validate_crawl_url


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _monitor_to_dict(monitor) -> Dict:
    return {
        "id": monitor.id,
        "agent_id": monitor.agent_id,
        "name": monitor.name,
        "url": monitor.url,
        "interval_minutes": monitor.interval_minutes,
        "is_active": bool(monitor.is_active),
        "last_status": monitor.last_status,
        "last_title": monitor.last_title,
        "last_excerpt": monitor.last_excerpt,
        "last_error": monitor.last_error,
        "last_checked_at": _format_dt(monitor.last_checked_at),
        "last_change_at": _format_dt(monitor.last_change_at),
        "created_at": _format_dt(monitor.created_at),
        "updated_at": _format_dt(monitor.updated_at),
    }


async def _normalize_agent_id(db, user_id: int, agent_id):
    if not agent_id:
        return None
    result = await db.execute(select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id))
    return int(agent_id) if result.scalar() else None


async def list_user_monitors(db, user_id: int):
    return [_monitor_to_dict(item) for item in await dao.list_monitors_by_user_async(db, user_id)]


async def create_monitor(db, user_id: int, payload: Dict) -> Dict:
    url = await async_validate_crawl_url(payload.get("url") or "")
    name = (payload.get("name") or "").strip()[:120]
    if not name:
        name = url
    interval = int(payload.get("interval_minutes") or 30)
    interval = max(5, min(1440, interval))
    agent_id = await _normalize_agent_id(db, user_id, payload.get("agent_id"))
    monitor = await dao.create_monitor_async(
        db=db,
        user_id=user_id,
        name=name,
        url=url,
        interval_minutes=interval,
        agent_id=agent_id,
    )
    await db.commit()
    await db.refresh(monitor)
    return _monitor_to_dict(monitor)


async def update_monitor(db, user_id: int, monitor_id: int, payload: Dict):
    monitor = await dao.get_owned_monitor_async(db, user_id, monitor_id)
    if not monitor:
        return None
    if "name" in payload:
        monitor.name = (payload.get("name") or monitor.name).strip()[:120]
    if "url" in payload:
        monitor.url = await async_validate_crawl_url(payload.get("url") or "")
    if "interval_minutes" in payload:
        monitor.interval_minutes = max(5, min(1440, int(payload.get("interval_minutes") or 30)))
    if "is_active" in payload:
        monitor.is_active = 1 if payload.get("is_active") else 0
    if "agent_id" in payload:
        monitor.agent_id = await _normalize_agent_id(db, user_id, payload.get("agent_id"))
    await db.commit()
    await db.refresh(monitor)
    return _monitor_to_dict(monitor)


async def delete_monitor(db, user_id: int, monitor_id: int) -> bool:
    monitor = await dao.get_owned_monitor_async(db, user_id, monitor_id)
    if not monitor:
        return False
    await db.delete(monitor)
    await db.commit()
    return True


async def check_monitor(db, user_id: int, monitor_id: int):
    monitor = await dao.get_owned_monitor_async(db, user_id, monitor_id)
    if not monitor:
        return None
    try:
        result = await async_crawl_url_to_markdown(monitor.url)
        content = result["content"].decode("utf-8", errors="replace")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        changed = bool(monitor.last_hash and monitor.last_hash != digest)
        now = datetime.utcnow()
        monitor.last_hash = digest
        monitor.last_title = (result.get("title") or monitor.name or "")[:255]
        monitor.last_excerpt = content[:500]
        monitor.last_status = "changed" if changed else "normal"
        monitor.last_error = None
        monitor.last_checked_at = now
        if changed or not monitor.last_change_at:
            monitor.last_change_at = now
        await db.commit()
        await db.refresh(monitor)
        payload = _monitor_to_dict(monitor)
        payload["changed"] = changed
        return payload
    except Exception as exc:
        monitor.last_status = "failed"
        monitor.last_error = str(exc)[:500]
        monitor.last_checked_at = datetime.utcnow()
        await db.commit()
        await db.refresh(monitor)
        payload = _monitor_to_dict(monitor)
        payload["changed"] = False
        return payload
