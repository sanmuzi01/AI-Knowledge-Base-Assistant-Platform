"""网页抓取异步服务。

当前爬虫基于 requests/BeautifulSoup/可选浏览器兜底，属于阻塞型 I/O。
这里统一放入线程池，避免网页抓取时卡住 async 路由和 SSE 推送。
"""

from typing import Dict

from starlette.concurrency import run_in_threadpool

from service.web_crawler_service import crawl_url_to_markdown, validate_crawl_url


async def async_validate_crawl_url(url: str) -> str:
    return await run_in_threadpool(validate_crawl_url, url)


async def async_crawl_url_to_markdown(url: str) -> Dict[str, object]:
    return await run_in_threadpool(crawl_url_to_markdown, url)
