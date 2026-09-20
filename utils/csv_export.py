"""管理后台报表导出的小工具：拼 CSV 字符串 + 包成下载响应。

只有两处用（用量报表、操作日志），抽出来是因为"UTF-8 BOM 不然 Excel 中文乱码"这类
细节容易漏，两处各写一遍反而更容易出错，不是为了应对还不存在的第三个调用方。
"""
import csv
import io
from typing import Any, Iterable, List, Sequence

from fastapi import Response


def rows_to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def csv_response(filename: str, content: str) -> Response:
    """Excel 在 Windows 上打开不带 BOM 的 UTF-8 CSV 会把中文显示成乱码，加个 BOM 头。"""
    body = "﻿" + content
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
