"""配置加载与管理。

配置文件位置（按优先级）：
    1. 环境变量 REPORT_ASSISTANT_CONFIG
    2. ./report-assistant.yml (当前目录)
    3. ~/.report-assistant/config.yml
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import yaml


DEFAULT_CONFIG_DIR = Path.home() / ".report-assistant"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yml"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "data.sqlite"
DEFAULT_SCREENSHOT_DIR = DEFAULT_CONFIG_DIR / "screenshots"


@dataclass
class LLMConfig:
    """LLM 配置，兼容 OpenAI 协议（OpenAI / DeepSeek / 通义 / 智谱等）。"""

    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o-mini"  # 用于截图分析的多模态模型
    temperature: float = 0.4
    timeout: int = 60


@dataclass
class GitConfig:
    """Git 提交收集配置。"""

    repos: list[str] = field(default_factory=list)
    # 识别"我"的提交：作者邮箱或姓名（任一匹配即视为本人提交）
    author_emails: list[str] = field(default_factory=list)
    author_names: list[str] = field(default_factory=list)
    # 是否包含 merge commits
    include_merges: bool = False
    # 桌面端定时同步 git 的间隔（秒），<=0 关闭
    poll_interval_seconds: int = 600


@dataclass
class ScreenshotConfig:
    """截图配置。"""

    enabled: bool = True
    interval_seconds: int = 600  # watch 模式下截图间隔，默认 10 分钟
    keep_after_analysis: bool = False  # 隐私默认：分析后立即删除
    output_dir: str = str(DEFAULT_SCREENSHOT_DIR)
    auto_start: bool = False  # 桌面端启动后自动开始监听
    # 监视器索引：0=所有屏幕合并；1+=具体某个屏幕（与 mss.monitors 对齐）
    monitor_index: int = 1
    # 空闲检测：用户连续无操作超过该秒数时跳过截图，<=0 禁用
    idle_skip_seconds: int = 300


@dataclass
class ReportConfig:
    """报告生成默认设置。"""

    default_template: str = "standard"  # standard / concise / technical / okr
    language: str = "zh-CN"
    user_name: str = ""
    team: str = ""


@dataclass
class AppConfig:
    """桌面客户端的应用级配置。"""

    # 开机自启（在登录时启动桌面端）
    auto_launch_on_boot: bool = False
    # 自动清理：删除多少天前的 work_logs/reports；<=0 关闭
    cleanup_keep_days: int = 60


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    git: GitConfig = field(default_factory=GitConfig)
    screenshot: ScreenshotConfig = field(default_factory=ScreenshotConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    app: AppConfig = field(default_factory=AppConfig)
    db_path: str = str(DEFAULT_DB_PATH)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        cfg = cls()
        if "llm" in data and data["llm"]:
            cfg.llm = LLMConfig(**{**asdict(cfg.llm), **data["llm"]})
        if "git" in data and data["git"]:
            cfg.git = GitConfig(**{**asdict(cfg.git), **data["git"]})
        if "screenshot" in data and data["screenshot"]:
            cfg.screenshot = ScreenshotConfig(
                **{**asdict(cfg.screenshot), **data["screenshot"]}
            )
        if "report" in data and data["report"]:
            cfg.report = ReportConfig(**{**asdict(cfg.report), **data["report"]})
        if "app" in data and data["app"]:
            cfg.app = AppConfig(**{**asdict(cfg.app), **data["app"]})
        if "db_path" in data and data["db_path"]:
            cfg.db_path = data["db_path"]
        return cfg


def find_config_path() -> Optional[Path]:
    env = os.environ.get("REPORT_ASSISTANT_CONFIG")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    local = Path.cwd() / "report-assistant.yml"
    if local.exists():
        return local
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    return None


def load_config(path: Optional[Path] = None) -> Config:
    """加载配置；找不到时返回带默认值的 Config。环境变量可覆盖关键字段。"""
    cfg_path = path or find_config_path()
    if cfg_path and cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = Config.from_dict(data)
    else:
        cfg = Config()

    # 环境变量覆盖（便于 CI / 临时使用）
    if env_key := os.environ.get("REPORT_ASSISTANT_API_KEY"):
        cfg.llm.api_key = env_key
    if env_base := os.environ.get("REPORT_ASSISTANT_BASE_URL"):
        cfg.llm.base_url = env_base
    if env_model := os.environ.get("REPORT_ASSISTANT_MODEL"):
        cfg.llm.model = env_model
    return cfg


def save_config(cfg: Config, path: Optional[Path] = None) -> Path:
    target = path or DEFAULT_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            cfg.to_dict(), f, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
    return target


def init_default_config(force: bool = False) -> Path:
    """在默认位置写入一份带注释的初始配置。"""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if DEFAULT_CONFIG_PATH.exists() and not force:
        return DEFAULT_CONFIG_PATH
    template = """# report-assistant 配置文件
# 文档: https://github.com/your/report-assistant

llm:
  # 兼容 OpenAI 协议的服务商均可：openai / deepseek / dashscope / zhipu ...
  provider: openai
  base_url: https://api.openai.com/v1
  api_key: ""            # 也可用环境变量 REPORT_ASSISTANT_API_KEY 覆盖
  model: gpt-4o-mini
  vision_model: gpt-4o-mini   # 截图分析使用的多模态模型
  temperature: 0.4
  timeout: 60

git:
  # 要扫描的本地仓库路径列表（绝对路径）
  repos: []
  # 用于识别"我自己"的提交（邮箱/姓名任一匹配即可）
  author_emails: []
  author_names: []
  include_merges: false
  # 桌面端定时同步 git 的间隔（秒），<=0 关闭
  poll_interval_seconds: 600

screenshot:
  enabled: true
  interval_seconds: 600       # watch 模式下截图间隔
  keep_after_analysis: false  # 隐私优先：分析完即删
  output_dir: ~/.report-assistant/screenshots
  auto_start: false           # 桌面端启动后自动开始监听
  monitor_index: 1            # 0=合并所有屏幕；1+=具体某个屏幕
  idle_skip_seconds: 300      # 用户连续 N 秒无操作时跳过截图，0=不检测

report:
  default_template: standard  # standard / concise / technical / okr
  language: zh-CN
  user_name: ""
  team: ""

db_path: ~/.report-assistant/data.sqlite
"""
    DEFAULT_CONFIG_PATH.write_text(template, encoding="utf-8")
    return DEFAULT_CONFIG_PATH
