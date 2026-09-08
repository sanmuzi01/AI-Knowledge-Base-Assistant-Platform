"""知识库诊断异步服务。"""

from typing import Dict, List

from starlette.concurrency import run_in_threadpool

from service.knowledge_diagnostics_service import check_crawl_urls, get_knowledge_diagnostics


async def async_get_knowledge_diagnostics(db, user_id: int, agent_id: int) -> Dict:
    return await run_in_threadpool(get_knowledge_diagnostics, db, user_id, agent_id)


async def async_check_crawl_urls(urls: List[str]) -> Dict:
    return await run_in_threadpool(check_crawl_urls, urls)
