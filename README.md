# report-assistant · 日报助手

<p align="center">
  <img src="report_assistant/desktop/assets/logo_128.png" width="96" alt="logo"/>
</p>

<p align="center">
  <b>AI 驱动的工作日报 / 周报 / 月报生成助手</b><br/>
  <i>静默记录工作轨迹，AI 帮你写好每一份汇报</i>
</p>

参考 [小黑日报助手](https://xiaohei.qitingai.com/) 的"截图记录 + AI 总结"思路，并增加 **Git 提交记录**、**多显示器支持**、**空闲检测** 等研发友好的能力。提供 **CLI** 与 **桌面客户端 (PySide6)** 两种形态，跨 Windows / macOS / Linux。

---

## 目录

- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [桌面客户端](#桌面客户端)
- [CLI 用法](#cli-用法)
- [报告模板](#报告模板)
- [配置详解](#配置详解)
- [工作机制](#工作机制)
- [隐私与数据安全](#隐私与数据安全)
- [开发](#开发)
- [常见问题](#常见问题)
- [许可](#许可)

---

## 核心特性

### 数据采集
- **Git 提交收集**：扫描多个本地仓库，按邮箱/姓名识别"我"的提交；支持定时自动同步（默认 10 分钟）
- **屏幕截图分析**：调用多模态 LLM 识别工作内容，自动归类（开发 / 会议 / 沟通 / 文档…）
- **多显示器支持**：可指定监控某一屏幕，或合并所有屏幕
- **空闲跳过**：连续 N 分钟无键鼠活动时自动跳过截图，避免无效记录与成本浪费（Windows 可靠）
- **手动备注**：生成报告时可补充未在数据中体现的内容（线下会议、口头沟通等）

### 报告生成
- **三路数据合并**：Git 提交 + 屏幕分析 + 手动备注，统一交给 LLM
- **四种内置模板**：标准 / 简洁 / 技术 / OKR
- **日期智能化**：日报选具体日；周报点周内任意日自动定位整周；月报选月份
- **多格式导出**：Markdown / Word (docx) / PDF
- **历史回看**：所有报告本地 SQLite 持久化，按 ID 列出可重读

### 桌面客户端
- 仿小黑视觉风格：emerald 绿主题、左侧导航、卡片式内容
- 系统托盘后台运行，关窗最小化
- 单例模式：重复启动会激活已有窗口，不会出现多开
- 开机自启（用户级，无需管理员权限）
- 自动清理：默认删除 60 天前的旧记录与报告
- 内置 LLM 连通性测试，配错 API Key 立即反馈

### 隐私优先
- 所有数据本地 SQLite，绝不上云
- 截图分析完默认立刻删除，只留文字描述
- LLM 请求直连用户配置的 `base_url`，无中转
- API Key 只存配置文件（用户级权限）

### 兼容
- **OpenAI 协议**：OpenAI / DeepSeek / 通义千问 / 智谱 / Moonshot / 任何兼容服务都能用
- **跨平台**：Windows 10+ / macOS 11+ / Ubuntu 20.04+

---

## 快速开始

### 1. 安装

```bash
# 仅 CLI
pip install -e .

# 包含桌面客户端（推荐）
pip install -e ".[gui]"

# 含开发依赖
pip install -e ".[dev,gui]"
```

依赖：本机已安装 `git`；Python 3.9+。

### 2. 配置

```bash
report init               # 生成 ~/.report-assistant/config.yml
```

打开配置文件填入 LLM `api_key` 和要扫描的 git 仓库；或直接启动桌面客户端在"设置"页面填写。

```bash
# 启动桌面端
report-gui
# 或
python -m report_assistant.desktop.app
```

### 3. 生成日报

桌面端首页点"📝 生成今日日报"；CLI：

```bash
report daily
report weekly --date 2024-06-12
report monthly -m 2024-06
```

---

## 桌面客户端

### 页面布局

| 页面 | 说明 |
| --- | --- |
| **🏠 首页** | 4 个统计卡片（今日提交 / 今日截图 / 已生成报告 / 监听状态）；快速操作（开始监听、立即截图、立即同步 Git、生成今日日报、生成本周周报）；显示器选择卡片；今日工作流水 |
| **🕒 时间线** | 按日期 + 类型筛选浏览 git 提交与屏幕活动；双击任意行弹出详情对话框，git 记录显示仓库/hash/作者/+/-/文件列表 |
| **📄 报告** | **生成** Tab：选类型/模板/日期/备注 → 一键生成，右侧 Markdown 实时预览，可复制 / 导出 md\|docx\|pdf；**历史** Tab：所有报告列表 + 详情预览 + 导出 |
| **⚙ 设置** | 5 个 Tab：LLM / Git / 截图 / 报告 & 个人 / 系统 |

### 设置页 Tab

**LLM**：provider、base_url、api_key、文本模型、视觉模型 + "测试连接"按钮（最多 15s 反馈结果）

**Git**：仓库列表（添加/删除）、作者邮箱/姓名、自动同步间隔、是否包含 merge

**截图**：启用开关、监听间隔、空闲跳过阈值、监控显示器、是否保留原图、应用启动后自动监听、截图目录

**报告 & 个人**：默认模板、汇报人、团队

**系统**：开机自启、自动清理 N 天前数据、当前数据库统计、立即清理 / 清空所有缓存

### 后台行为

- **关窗最小化到托盘**：截图监听仍在后台跑；从托盘"退出"才真正结束
- **Git 定时同步**：按设置的间隔自动 `git log` 拉取，新 commit 入库
- **空闲跳过**：调用 Windows `GetLastInputInfo`，连续无操作超阈值时跳过截图
- **自动清理**：每次启动检查 `cleanup_keep_days`，删除过期记录
- **单例模式**：基于 QLocalServer，重复启动会激活已有窗口

---

## CLI 用法

```bash
report init                          # 初始化配置
report config show                   # 查看当前生效配置

# 数据采集
report git --days 7                  # 看过去 7 天 git 提交
report capture                       # 截一张图并分析
report watch                         # 长驻监听（Ctrl+C 退出）

# 生成报告
report daily                         # 今日日报
report daily -t technical -o today.md
report weekly --date 2024-06-12      # 该日所属周
report monthly -m 2024-06            # 该月
report daily --dry-run               # 不调 LLM，仅看采集到的数据

# 历史管理
report list                          # 列出已生成报告
report list --kind weekly
report show 12                       # 查看 ID=12 的报告
report export 12 --to weekly.md      # 导出（按扩展名识别格式：md/docx/pdf）
```

---

## 报告模板

| 名称 | 风格 | 适用 |
| --- | --- | --- |
| `standard` | 标准 | 本期完成 / 进行中 / 下期计划 / 风险与求助 — 通用日报周报 |
| `concise` | 简洁 | 完成 / 计划 / 问题（≤200 字）— 微信钉钉群同步 |
| `technical` | 技术 | 代码与提交 / 技术亮点 / 测试 / 下期技术计划 — 研发团队 |
| `okr` | OKR | 目标进展 / 重点产出 / 反思 / 下期目标 — 双周月度复盘 |

模板里嵌了"基于事实、不要编造、合并相似事项"的指令，避免 LLM 流水账。

---

## 配置详解

配置文件位置（按优先级）：

1. 环境变量 `REPORT_ASSISTANT_CONFIG`
2. `./report-assistant.yml`（当前目录）
3. `~/.report-assistant/config.yml`（默认）

```yaml
llm:
  provider: openai            # openai / deepseek / dashscope / zhipu ...
  base_url: https://api.openai.com/v1
  api_key: ""                 # 或环境变量 REPORT_ASSISTANT_API_KEY
  model: gpt-4o-mini
  vision_model: gpt-4o-mini   # 截图分析多模态模型
  temperature: 0.4
  timeout: 60

git:
  repos:                      # 要扫描的本地仓库（绝对路径）
    - C:/workspace/proj-a
    - C:/workspace/proj-b
  author_emails:              # 邮箱/姓名任一匹配即视为本人提交
    - me@example.com
  author_names:
    - Ethan
  include_merges: false
  poll_interval_seconds: 600  # 桌面端定时同步 git；<=0 关闭

screenshot:
  enabled: true
  interval_seconds: 600       # watch 模式截图间隔
  keep_after_analysis: false  # 隐私优先：分析完即删
  output_dir: ~/.report-assistant/screenshots
  auto_start: false           # 桌面端启动自动开始监听
  monitor_index: 1            # 0=合并所有屏；1+=具体某屏
  idle_skip_seconds: 300      # 空闲超 N 秒跳过；0=不检测

report:
  default_template: standard
  language: zh-CN
  user_name: ""
  team: ""

app:
  auto_launch_on_boot: false  # 开机自启
  cleanup_keep_days: 60       # 自动清理 N 天前数据；<=0 关闭

db_path: ~/.report-assistant/data.sqlite
```

环境变量覆盖：
- `REPORT_ASSISTANT_API_KEY`
- `REPORT_ASSISTANT_BASE_URL`
- `REPORT_ASSISTANT_MODEL`

---

## 工作机制

```
           ┌─────────── CLI 或 桌面客户端 ───────────┐
           │                                          │
           ▼                                          ▼
  Git 收集（多仓库 + 作者过滤）       定时/手动截屏 → 视觉 LLM
  幂等入库（按 commit hash 去重）     空闲检测 → 跳过
           │                                          │
           └────────────────┬─────────────────────────┘
                            ▼
                  SQLite 本地存储 (work_logs)
                            │
                            ▼
                  Generator + 模板（standard/concise/technical/okr）
                            │
                            ▼
                  LLM (chat completions)
                            │
                            ▼
              Markdown 报告 → 入库 (reports)
                            │
                            ▼
                导出：Markdown / Word / PDF
```

关键决策：
- **幂等入库**：git commit 用 hash 作为 dedupe_key，重复同步不会产生脏数据
- **截图分析后即删**：隐私优先；只保留视觉模型生成的文字描述
- **空闲检测在 Worker 线程内**：跳过时不阻塞 UI，状态栏提示
- **报告渲染走 QTextDocument**：Markdown 预览和 PDF 导出共享同一份排版样式

---

## 隐私与数据安全

- **本地存储**：所有 git 提交、截图描述、生成的报告都在 `~/.report-assistant/data.sqlite`，绝不上云。
- **截图即删**：默认 `keep_after_analysis=false`，视觉模型分析完成立刻删除；可通过设置开启保留。
- **API Key**：仅写入用户级配置文件（建议手动 chmod 600）；可改用环境变量。
- **直连不中转**：LLM 请求由本机直接发到你配置的 `base_url`，不经过任何中间服务。
- **空闲跳过**：连续无操作时不截图，避免捕获息屏内容。
- **自动清理**：默认 60 天后过期数据自动清除，可在设置里调整或关闭。
- **手动清理**：随时可"立即清理 N 天前数据"或"清空所有缓存"。

---

## 开发

```bash
pip install -e ".[dev,gui]"
pytest -q
```

### 项目结构

```
report_assistant/
├── config.py              # 配置数据类与加载/保存
├── storage.py             # SQLite 存储（work_logs / reports + 清理）
├── git_collector.py       # Git 提交收集（多仓库 + 作者过滤）
├── screenshot.py          # 截屏 + 视觉分析 + 多显示器 + 空闲检测
├── llm.py                 # OpenAI 兼容客户端（含连通性测试）
├── templates.py           # 4 种报告模板
├── generator.py           # 时间范围解析 + 数据合并 + 报告生成
├── exporters.py           # md / docx / pdf 导出
├── autostart.py           # 跨平台开机自启（注册表/LaunchAgent/XDG）
├── cli.py                 # CLI 入口
└── desktop/               # PySide6 桌面客户端
    ├── app.py             # 应用入口（单例 + 图标）
    ├── main_window.py     # 主窗口、托盘、Git 定时器、自动清理
    ├── theme.py           # QSS 主题
    ├── singleton.py       # QLocalServer 单例机制
    ├── workers.py         # QThread workers (Capture/Watch/Report/TestConn)
    ├── widgets/           # 自定义控件（NumberInput）
    ├── pages/             # home / timeline / reports / settings
    └── assets/            # logo + chevron/plus/minus 图标（程序生成）
```

### 测试

27 个测试覆盖：
- Storage CRUD / 去重 / 清理
- 时间范围工具（日/周/月）
- Git 提交解析（含真实临时仓库）
- 视觉响应 JSON 容错
- LLM 连通性测试（mock）
- 单例守卫（acquire/release/重新 acquire）

```bash
pytest -q                          # 全部
pytest tests/test_storage.py -v    # 单文件
```

### 重新生成图标资源

```bash
python -m report_assistant.desktop.assets.generate_logo    # 应用 logo
python -m report_assistant.desktop.assets.generate_arrows  # 控件箭头
```

---

## 常见问题

**Q：第一次启动后首页统计为 0？**
A：先到"设置 → Git"加入仓库路径和作者邮箱保存；再到"设置 → LLM"填 api_key；回首页点"立即同步 Git"和"立即截图分析"会立刻有数据。

**Q：监听一会就停了？**
A：检查"截图"Tab 的"空闲跳过阈值"。默认 5 分钟无键鼠活动就跳过。可调高或设为 0 关闭。

**Q：测试连接一直卡？**
A：测试有最长 15s 超时；超时后会显示具体错误（401 invalid api key / connection refused 等）。如果一直转圈是网络问题或 base_url 写错。

**Q：开机自启在 macOS / Linux 上没生效？**
A：检查 `~/Library/LaunchAgents/report-assistant.plist`（macOS）或 `~/.config/autostart/report-assistant.desktop`（Linux）是否存在。当前实现假设以源码方式启动，打包后请用 `--frozen` 模式重新写入。

**Q：报告导出 PDF 时中文乱码？**
A：PDF 渲染依赖系统中文字体。Windows 自带"Microsoft YaHei UI"；macOS "PingFang SC"；Linux 需要安装 `fonts-noto-cjk` 之类。

**Q：怎么彻底卸载？**
A：从托盘退出 → `pip uninstall report-assistant` → 删除 `~/.report-assistant/`（含数据库、截图、配置）→ 设置过开机自启的话也清理对应注册表/plist/desktop 文件。

---

## 许可

MIT
