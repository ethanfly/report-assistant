//! 报告模板：每个模板对应一组提示词（system + user 提示），
//! 用于驱动 LLM 生成不同风格 / 视角的工作报告。
//!
//! 模板通过 `key` 标识，调用方可以从配置（`cfg.report.default_template`）
//! 或前端选择一个模板交给 [`crate::generator::generate_report`] 使用。

use serde::{Deserialize, Serialize};

/// 报告周期种类。
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Kind {
    /// 日报
    Daily,
    /// 周报
    Weekly,
    /// 月报
    Monthly,
}

impl Kind {
    /// 输出小写英文名，用于持久化、日志、文件名等场景。
    pub fn as_str(&self) -> &'static str {
        match self {
            Kind::Daily => "daily",
            Kind::Weekly => "weekly",
            Kind::Monthly => "monthly",
        }
    }

    /// 中文显示名，便于直接拼到 Prompt 中。
    pub fn label_zh(&self) -> &'static str {
        match self {
            Kind::Daily => "日报",
            Kind::Weekly => "周报",
            Kind::Monthly => "月报",
        }
    }
}

/// 报告模板。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportTemplate {
    /// 唯一标识：standard / concise / technical / okr。
    pub key: String,
    /// 展示名称。
    pub label: String,
    /// 系统提示词，描述写作风格 / 角色。
    pub system_prompt: String,
    /// 用户提示词补充：在末尾追加，进一步约束输出结构。
    pub user_prompt_hint: String,
}

/// 内置全部模板。顺序即推荐排序（standard 在最前）。
pub fn all() -> Vec<ReportTemplate> {
    vec![
        ReportTemplate {
            key: "standard".to_string(),
            label: "标准".to_string(),
            system_prompt: "你是一名严谨的工程师助理，负责把零散的工作记录整理成正式的中文工作报告。\
输出使用 Markdown，标题层级清晰，语言简练、客观，不要编造没有依据的内容。\
【核心原则】以「已完成待办」为主要事实来源撰写完成事项；Git 提交与截图仅作补充佐证，\
不要用截图臆造完成项。如果输入信息不足，可在对应小节注明\"暂无\"。"
                .to_string(),
            user_prompt_hint: "请撰写一份结构清晰的中文工作报告，至少包含以下小节：\n\
1. 今日完成（优先逐条覆盖「已完成待办」，可合并同类项；Git/截图仅补充细节）\n\
2. 进行中\n\
3. 明日计划\n\
4. 风险 / 问题\n\
每个小节使用项目符号列出要点，必要时按模块或项目再做二级分组。"
                .to_string(),
        },
        ReportTemplate {
            key: "concise".to_string(),
            label: "极简".to_string(),
            system_prompt: "你是一名追求极致简洁的中文工作助理，目标是让阅读者在 10 秒内掌握全部要点。\
输出仅使用项目符号，不要写小节标题，不要套话。\
优先用「已完成待办」概括产出，Git/截图仅在待办缺失时补充。"
                .to_string(),
            user_prompt_hint: "请用 5 行以内的项目符号总结本周期工作。\
每行不超过 30 个汉字，突出动词与产出；优先覆盖已完成待办，不要补充说明，不要使用任何小节标题。"
                .to_string(),
        },
        ReportTemplate {
            key: "technical".to_string(),
            label: "技术向".to_string(),
            system_prompt: "你是一名资深技术负责人，撰写面向研发团队的中文工作报告。\
要求体现技术深度：包含模块 / 功能维度的归类、关键技术决策、性能或稳定性影响，\
并对未完成事项给出后续计划。\
【核心原则】完成项以「已完成待办」为主证据，Git 提交用于补充技术细节与模块归属。"
                .to_string(),
            user_prompt_hint: "请按 模块 / 功能 分组撰写中文技术工作报告，至少包含：\n\
1. 变更摘要（先汇总已完成待办，再按模块列出关键改动与原因；Git 作补充）\n\
2. 关键决策（含权衡与替代方案）\n\
3. 未完成事项 / 下一步\n\
如有性能、兼容性或安全风险，请在对应模块下显式标注。"
                .to_string(),
        },
        ReportTemplate {
            key: "okr".to_string(),
            label: "OKR 视角".to_string(),
            system_prompt: "你是一名熟悉 OKR 方法论的中文工作助理，负责把日常产出对齐到目标 / 关键结果上。\
如果输入材料中无法判断对应的 O 或 KR，请保留\"未对齐\"占位，不要臆造。\
【核心原则】关键结果进展优先对齐「已完成待办」，Git/截图仅作佐证。"
                .to_string(),
            user_prompt_hint: "请按 OKR 视角输出中文工作报告，结构如下：\n\
1. 目标（Objective）\n\
2. 关键结果进展（每个 KR 列出当前进度；工作项优先来自已完成待办）\n\
3. 阻塞 / 风险\n\
4. 下一步行动（具体到事项与负责人，如未知则写\"待确认\"）"
                .to_string(),
        },
    ]
}

/// 按 `key` 查找模板（精确匹配，不区分大小写）。
pub fn get(key: &str) -> Option<ReportTemplate> {
    let key = key.trim().to_ascii_lowercase();
    all().into_iter().find(|t| t.key == key)
}

/// 默认模板：standard。
pub fn default_template() -> ReportTemplate {
    // standard 一定存在，unwrap 安全。
    get("standard").expect("standard 模板缺失")
}
