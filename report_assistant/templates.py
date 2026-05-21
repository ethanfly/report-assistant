"""报告模板：定义不同风格的输出结构与给 LLM 的指令。

模板对应参考产品的"标准 / 简洁 / 技术 / OKR"四种。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReportKind = Literal["daily", "weekly", "monthly"]
TemplateName = Literal["standard", "concise", "technical", "okr"]


@dataclass
class Template:
    name: TemplateName
    title: str
    description: str
    instruction: str  # 给 LLM 的格式说明


TEMPLATES: dict[str, Template] = {
    "standard": Template(
        name="standard",
        title="标准模板",
        description="包含今日完成、进行中、明日计划、风险与求助",
        instruction="""请按以下结构输出 Markdown：

# {kind_title}（{period}）

## 一、本期完成
- 用编号列表列出完成的关键事项；每条 1 行，包含动作 + 对象 + 结果/影响。

## 二、进行中
- 列出尚未完成但已推进的事项，注明当前进度。

## 三、下期计划
- 列出下个周期的优先任务，按重要性排序。

## 四、风险与求助
- 列出阻塞、风险或需要他人协助的事项；若无，写"无"。
""",
    ),
    "concise": Template(
        name="concise",
        title="简洁模板",
        description="只输出最核心的要点，适合微信/钉钉群发",
        instruction="""请按以下结构输出 Markdown，整体不超过 200 字：

# {kind_title}（{period}）

**完成**：用 3-5 个短句概括最关键的产出。

**计划**：用 2-3 个短句说下一步。

**问题**：一句话；若无写"无"。
""",
    ),
    "technical": Template(
        name="technical",
        title="技术模板",
        description="侧重代码改动、模块、技术决策，适合研发团队",
        instruction="""请按以下结构输出 Markdown：

# {kind_title}（{period}）

## 代码与提交
- 按仓库分组列出关键 commit，简要说明改动意图（不要复述 commit message 原文）。
- 若可识别，标注涉及的模块/文件。

## 技术亮点 & 决策
- 关键设计选择、性能优化、重构、踩坑记录。

## 测试与质量
- 新增/修改的测试、CI 状态、已知 Bug。

## 下期技术计划
- 列出下一阶段的技术待办与优先级。

## 阻塞 & 求助
- 技术层面的阻塞或需要 review 的内容；若无写"无"。
""",
    ),
    "okr": Template(
        name="okr",
        title="OKR 模板",
        description="围绕目标与关键结果输出，适合双周/月度复盘",
        instruction="""请按以下结构输出 Markdown：

# {kind_title}（{period}）

## 目标进展
- 推断本期所对应的核心目标 (Objective) 1-3 个。
- 每个目标下列出 2-4 个关键结果 (Key Results) 的进度（用 0-100% 估算，并简短说明依据）。

## 重点产出
- 列出对目标推进影响最大的 3-5 项工作。

## 反思 & 调整
- 哪些假设被验证或推翻，下期的策略调整。

## 下期目标
- 简要说明下期希望达成的 O 与 KR。
""",
    ),
}


def get_template(name: str) -> Template:
    if name not in TEMPLATES:
        raise ValueError(
            f"未知模板: {name}。可用: {', '.join(TEMPLATES.keys())}"
        )
    return TEMPLATES[name]


KIND_TITLE = {
    "daily": "日报",
    "weekly": "周报",
    "monthly": "月报",
}
