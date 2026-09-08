import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.web_crawler_service import CrawlerError, crawl_url_to_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="检查网页是否能被项目爬虫抓取")
    parser.add_argument("url", help="要抓取的 http/https URL")
    parser.add_argument("--browser", action="store_true", help="启用浏览器渲染兜底，适合检查强 JS 渲染页面")
    args = parser.parse_args()

    if args.browser:
        os.environ["CRAWLER_BROWSER_FALLBACK"] = "1"

    try:
        result = crawl_url_to_markdown(args.url)
    except CrawlerError as exc:
        raise SystemExit(f"抓取失败: {exc}") from exc

    print("抓取成功")
    print(f"URL: {result['url']}")
    print(f"标题: {result['title'] or '-'}")
    print(f"文件名: {result['file_name']}")
    print(f"大小: {result['size']} bytes")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
