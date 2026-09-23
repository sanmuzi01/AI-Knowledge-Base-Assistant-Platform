"""用户工作台配置服务。"""

import json
from typing import Dict, List

from models import workspace_async_dao as dao


DEFAULT_MODULES: List[str] = ["models", "knowledge", "skills", "web-monitor", "memory", "tasks"]
DEFAULT_WIDGETS: List[Dict] = [
    {"id": "quick-actions", "type": "quick-actions", "title": "快捷操作", "enabled": True, "size": "wide", "settings": {}},
    {"id": "web-monitor", "type": "web-monitor", "title": "网页监控", "enabled": True, "size": "wide", "settings": {}},
    {"id": "chart-output", "type": "chart-output", "title": "图表输出", "enabled": True, "size": "wide", "settings": {}},
    {"id": "recent-runs", "type": "recent-runs", "title": "最近运行", "enabled": True, "size": "wide", "settings": {}},
    {"id": "recent-tasks", "type": "recent-tasks", "title": "后台任务", "enabled": True, "size": "wide", "settings": {}},
]

MODULE_CATALOG: Dict[str, Dict] = {
    "models": {"title": "AI 服务", "keywords": ["模型", "ai服务", "ai 服务", "密钥", "key"]},
    "knowledge": {"title": "个人资料", "keywords": ["资料", "知识库", "文档", "rag"]},
    "skills": {"title": "技能中心", "keywords": ["skill", "技能", "能力", "工具"]},
    "web-monitor": {"title": "网页监控", "keywords": ["网页", "监控", "实时", "价格", "公告", "变化"]},
    "memory": {"title": "长期记忆", "keywords": ["记忆", "偏好", "画像"]},
    "tasks": {"title": "后台任务", "keywords": ["任务", "后台", "队列", "进度"]},
}

WIDGET_CATALOG: Dict[str, Dict] = {
    "quick-actions": {"title": "快捷操作", "keywords": ["快捷", "操作", "入口"]},
    "web-monitor": {"title": "网页监控", "keywords": ["网页", "监控", "实时", "价格", "公告", "变化"]},
    "chart-output": {"title": "图表输出", "keywords": ["图表", "可视化", "柱状图", "折线图", "饼图", "chart"]},
    "recent-runs": {"title": "最近运行", "keywords": ["运行", "调用", "对话记录"]},
    "recent-tasks": {"title": "后台任务", "keywords": ["任务", "后台", "队列", "进度"]},
}


def _safe_json_loads(raw: str, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except Exception:
        return fallback


def _workspace_to_dict(workspace) -> Dict:
    return {
        "modules": _safe_json_loads(workspace.modules_json, DEFAULT_MODULES),
        "widgets": _safe_json_loads(workspace.widgets_json, DEFAULT_WIDGETS),
        "layout": _safe_json_loads(workspace.layout_json, {}),
        "updated_at": workspace.updated_at.strftime("%Y-%m-%d %H:%M:%S") if workspace.updated_at else None,
    }


def default_workspace() -> Dict:
    return {
        "modules": list(DEFAULT_MODULES),
        "widgets": [dict(item) for item in DEFAULT_WIDGETS],
        "layout": {},
        "updated_at": None,
    }


def _ensure_widget(widgets: List[Dict], widget_type: str) -> bool:
    meta = WIDGET_CATALOG.get(widget_type)
    if not meta:
        return False
    for item in widgets:
        if item.get("type") == widget_type:
            item["enabled"] = True
            return True
    widgets.append({
        "id": widget_type,
        "type": widget_type,
        "title": meta["title"],
        "enabled": True,
        "size": "wide",
        "settings": {},
    })
    return True


def _match_catalog(text: str, catalog: Dict[str, Dict]) -> List[str]:
    matched = []
    for key, meta in catalog.items():
        if any(keyword.lower() in text for keyword in meta["keywords"]):
            matched.append(key)
    return matched


async def get_user_workspace(db, user_id: int) -> Dict:
    workspace = await dao.get_workspace_by_user_async(db, user_id)
    if not workspace:
        return default_workspace()
    return _workspace_to_dict(workspace)


async def save_user_workspace(db, user_id: int, payload: Dict) -> Dict:
    modules = payload.get("modules")
    widgets = payload.get("widgets")
    layout = payload.get("layout") or {}
    if not isinstance(modules, list):
        modules = list(DEFAULT_MODULES)
    if not isinstance(widgets, list):
        widgets = [dict(item) for item in DEFAULT_WIDGETS]
    modules = [item for item in modules if isinstance(item, str)]
    normalized_widgets = []
    for item in widgets:
        if not isinstance(item, dict):
            continue
        normalized_widgets.append({
            "id": str(item.get("id") or item.get("type") or "widget"),
            "type": str(item.get("type") or "custom"),
            "title": str(item.get("title") or "自定义小窗口")[:80],
            "enabled": bool(item.get("enabled", True)),
            "size": str(item.get("size") or "wide"),
            "settings": item.get("settings") if isinstance(item.get("settings"), dict) else {},
        })
    workspace = await dao.get_workspace_by_user_async(db, user_id)
    modules_json = json.dumps(modules, ensure_ascii=False)
    widgets_json = json.dumps(normalized_widgets, ensure_ascii=False)
    layout_json = json.dumps(layout if isinstance(layout, dict) else {}, ensure_ascii=False)
    if workspace:
        workspace.modules_json = modules_json
        workspace.widgets_json = widgets_json
        workspace.layout_json = layout_json
    else:
        workspace = await dao.create_workspace_async(db, user_id, modules_json, widgets_json, layout_json)
    await db.commit()
    await db.refresh(workspace)
    return _workspace_to_dict(workspace)


async def apply_workspace_command(db, user_id: int, prompt: str) -> Dict:
    text = (prompt or "").strip().lower()
    if not text:
        return {
            "message": "请先写下你想怎么调整工作台",
            "actions": [],
            "workspace": await get_user_workspace(db, user_id),
        }

    workspace = await get_user_workspace(db, user_id)
    modules = list(workspace["modules"])
    widgets = [dict(item) for item in workspace["widgets"]]
    actions = []
    removing = any(word in text for word in ["隐藏", "去掉", "删除", "不要", "关闭"])
    adding = any(word in text for word in ["添加", "新增", "显示", "打开", "需要", "想要", "给我"])
    if not removing and not adding:
        adding = True

    for module_key in _match_catalog(text, MODULE_CATALOG):
        title = MODULE_CATALOG[module_key]["title"]
        if removing:
            if module_key in modules:
                modules.remove(module_key)
                actions.append(f"已隐藏模块：{title}")
        elif module_key not in modules:
            modules.append(module_key)
            actions.append(f"已添加模块：{title}")

    for widget_type in _match_catalog(text, WIDGET_CATALOG):
        title = WIDGET_CATALOG[widget_type]["title"]
        if removing:
            changed = False
            for item in widgets:
                if item.get("type") == widget_type and item.get("enabled", True):
                    item["enabled"] = False
                    changed = True
            if changed:
                actions.append(f"已隐藏小窗口：{title}")
        elif _ensure_widget(widgets, widget_type):
            actions.append(f"已添加小窗口：{title}")

    if any(word in text for word in ["图表", "可视化", "柱状图", "折线图", "饼图", "chart"]):
        if "skills" not in modules:
            modules.append("skills")
            actions.append("已添加模块：技能中心")
        _ensure_widget(widgets, "chart-output")
        actions.append("已准备图表输出入口，后续给助手绑定图表工具即可按对话生成图表")

    if any(word in text for word in ["网页", "监控", "实时", "价格", "公告", "变化"]):
        if "web-monitor" not in modules:
            modules.append("web-monitor")
            actions.append("已添加模块：网页监控")
        _ensure_widget(widgets, "web-monitor")

    actions = list(dict.fromkeys(actions))
    if not actions:
        actions.append("暂未识别到可执行调整，请换一种说法，例如：给我添加网页监控和图表输出")

    saved = await save_user_workspace(db, user_id, {
        "modules": modules,
        "widgets": widgets,
        "layout": workspace.get("layout") or {},
    })
    return {
        "message": "工作台已按你的要求更新",
        "actions": actions,
        "workspace": saved,
    }
