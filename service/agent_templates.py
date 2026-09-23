from utils.timeutil import utcnow
import json
import os
import uuid
from typing import Dict, List

from utils.path_tool import get_abs_path


AGENT_TEMPLATES: List[Dict] = [
    {
        "id": "paper_writer",
        "name": "论文写作助手",
        "description": "用于论文选题、提纲、摘要、润色和结构优化。",
        "role": "你是一个专业、严谨的论文写作助手，熟悉学术写作规范、论文结构和中文学术表达。",
        "task": "帮助用户梳理论文主题、生成提纲、优化摘要、润色段落、调整论证结构，并指出表达不清或逻辑薄弱之处。",
        "constraints": "不要编造不存在的文献、数据或引用。遇到缺少资料的情况要明确提醒用户补充信息。保持学术、克制、准确的语气。",
        "output": "优先使用清晰的小标题和分点结构输出。涉及修改时，先给修改建议，再给可直接使用的版本。",
        "model_name": "glm-4",
        "rag_enabled": 0,
        "memory_enabled": 1,
        "temperature": 60,
        "skill_names": ["论文写作助手"],
    },
    {
        "id": "data_analyst",
        "name": "数据分析助手",
        "description": "用于理解数据、提炼结论、设计分析思路和生成报告。",
        "role": "你是一个数据分析助手，擅长把零散数据整理成清晰的问题、指标、结论和行动建议。",
        "task": "帮助用户分析数据背景、选择指标、发现趋势、总结异常、撰写分析结论，并给出下一步验证思路。",
        "constraints": "不要在数据不足时强行下结论。需要区分事实、推断和建议。涉及计算时要展示关键过程。",
        "output": "按“结论摘要、关键发现、可能原因、建议动作”的结构输出；如果用户提供表格或数据，优先给出可执行分析步骤。",
        "model_name": "glm-4",
        "rag_enabled": 0,
        "memory_enabled": 1,
        "temperature": 55,
        "skill_names": ["数据分析助手"],
    },
    {
        "id": "chart_builder",
        "name": "图表生成助手",
        "description": "用于根据数据生成图表，并解释图表结论。",
        "role": "你是一个图表生成助手，擅长根据用户给出的数据选择合适图表，并生成清晰可读的可视化结果。",
        "task": "识别用户数据中的类别、数值和时间维度，选择柱状图、折线图、饼图等合适图表，并解释图表表达的信息。",
        "constraints": "数据不完整时先询问或说明假设。图表标题、坐标轴和图例要清楚。不要改变用户给出的原始数值。",
        "output": "先简要说明选择的图表类型，再生成图表，最后给出 2 到 4 条图表解读。",
        "model_name": "glm-4",
        "rag_enabled": 0,
        "memory_enabled": 1,
        "temperature": 50,
        "skill_names": ["数据图表助手"],
    },
    {
        "id": "knowledge_qa",
        "name": "知识库问答助手",
        "description": "用于上传资料后的检索问答、总结和引用式回答。",
        "role": "你是一个知识库问答助手，擅长基于用户上传的资料进行检索、总结和问答。",
        "task": "优先根据知识库检索结果回答用户问题，帮助用户总结文档、定位重点、对比信息和整理结论。",
        "constraints": "如果知识库资料中没有答案，要明确说明没有找到依据。不要把外部常识伪装成资料内容。",
        "output": "先直接回答问题，再列出依据摘要；如果资料不足，给出需要补充的文档或信息。",
        "model_name": "glm-4",
        "rag_enabled": 1,
        "memory_enabled": 1,
        "temperature": 45,
        "skill_names": [],
    },
]


USER_TEMPLATE_DIR = "agent_templates"


def _template_file(user_id: int) -> str:
    directory = get_abs_path(USER_TEMPLATE_DIR)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"u{user_id}.json")


def _load_user_templates(user_id: int) -> List[Dict]:
    path = _template_file(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _save_user_templates(user_id: int, templates: List[Dict]) -> None:
    path = _template_file(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def list_templates_for_user(user_id: int) -> List[Dict]:
    builtin = []
    for template in AGENT_TEMPLATES:
        item = template.copy()
        item["source"] = "builtin"
        item["editable"] = False
        builtin.append(item)
    return builtin + _load_user_templates(user_id)


def create_user_template(user_id: int, payload: Dict) -> Dict:
    now = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    template = {
        "id": f"custom_{uuid.uuid4().hex[:12]}",
        "name": str(payload.get("name") or "自定义 Agent 模板").strip()[:255],
        "description": str(payload.get("description") or "用户自定义 Agent 模板").strip()[:500],
        "role": str(payload.get("role") or ""),
        "task": str(payload.get("task") or ""),
        "constraints": str(payload.get("constraints") or ""),
        "output": str(payload.get("output") or ""),
        "model_name": str(payload.get("model_name") or "glm-4").strip()[:100],
        "rag_enabled": 1 if int(payload.get("rag_enabled") or 0) == 1 else 0,
        "memory_enabled": 1 if int(payload.get("memory_enabled") or 0) == 1 else 0,
        "temperature": max(0, min(100, int(payload.get("temperature") or 70))),
        "skill_names": [
            str(name).strip()
            for name in (payload.get("skill_names") or [])
            if str(name).strip()
        ],
        "source": "custom",
        "editable": True,
        "created_at": now,
        "updated_at": now,
    }
    templates = _load_user_templates(user_id)
    templates.insert(0, template)
    _save_user_templates(user_id, templates)
    return template


def delete_user_template(user_id: int, template_id: str) -> bool:
    templates = _load_user_templates(user_id)
    kept = [template for template in templates if template.get("id") != template_id]
    if len(kept) == len(templates):
        return False
    _save_user_templates(user_id, kept)
    return True
