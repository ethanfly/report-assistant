# report-assistant · 小T日报助手

AI 驱动的工作日报/周报/月报生成工具。Rust + Tauri 实现，启动瞬开、UI 永不卡顿。

参考 [小黑日报助手](https://xiaohei.qitingai.com/) 的 "截图记录 + AI 总结" 思路，加上 **Git 提交记录**、**多显示器支持**、**空闲检测** 等研发友好的能力。提供 **CLI** 与 **桌面 GUI** 两种形态，跨 Windows / macOS / Linux。

## 特性

- **截图工作流**：定时截屏 → 视觉模型识别工作类别 → 入库
- **Git 提交收集**：扫多仓库，按邮箱/姓名识别"我的"提交
- **报告生成**：日/周/月报，4 种模板（standard/concise/technical/okr）
- **导出**：Markdown / HTML / 纯文本
- **隐私**：截图分析后默认即删；数据全在本地 SQLite
- **多显示器**：可选择监控的屏幕
- **空闲跳过**：用户离开时不浪费 token

## 技术栈

- **核心**：Rust 1.94+（Cargo workspace，3 个 crate）
  - `crates/core`：纯业务库（截图、Git、LLM、SQLite、报告生成、导出）
  - `crates/cli`：命令行（clap derive）
  - `src-tauri`：Tauri v2 桌面壳（独立子项目）
- **前端**：React 18 + TypeScript + Tailwind CSS + Vite
- **存储**：SQLite + WAL
- **截图**：xcap（跨平台原生）
- **LLM**：OpenAI 兼容协议（reqwest + rustls）

## 安装

下载 [Releases](https://github.com/ethanfly/report-assistant/releases) 中对应平台的 zip，解压双击运行。

## 配置

首次运行会在 `~/.report-assistant/config.yml` 生成默认配置。可在 GUI "设置" 页或用 CLI 修改：

```bash
report-assistant config set llm.api_key sk-xxx
report-assistant config set llm.base_url https://api.openai.com/v1
report-assistant config set llm.model gpt-4o-mini
```

环境变量优先级最高：`REPORT_ASSISTANT_API_KEY` / `REPORT_ASSISTANT_BASE_URL` / `REPORT_ASSISTANT_MODEL`。

## CLI 用法

```bash
# 立即截图分析一次
report-assistant capture

# 前台监听（Ctrl+C 退出）
report-assistant watch --interval 600

# 同步 Git 提交
report-assistant git sync
report-assistant git list --days 7

# 生成报告
report-assistant report daily
report-assistant report weekly --template technical --notes "本周重点：性能优化"
report-assistant report monthly --date 2025-01-15

# 报告管理
report-assistant report list --limit 20
report-assistant report show <id>
report-assistant report export <id> --format md --out ~/Documents

# 数据查看
report-assistant logs --limit 50 --source git
report-assistant stats

# 数据清理
report-assistant cleanup --days 60

# 工具
report-assistant llm test
report-assistant monitors
```

所有命令支持 `--json` 输出（便于脚本接入）。

## 开发

要求：Rust stable + Node 22+ + pnpm 10+。

```bash
# 安装前端依赖
pnpm install

# 开发模式（同时启动 vite dev server + tauri）
pnpm tauri dev

# Release 构建
pnpm tauri build

# 仅 CLI
cargo build --release -p report-assistant-cli
# 产物：target/release/report-assistant(.exe)

# 仅核心库测试（如有）
cargo test -p report-assistant-core
```

## 项目结构

```
report-assistant/
├── Cargo.toml              # workspace 根（不含 src-tauri）
├── crates/
│   ├── core/               # 业务核心库
│   │   └── src/
│   │       ├── config.rs
│   │       ├── storage.rs  # SQLite + WAL
│   │       ├── screenshot.rs
│   │       ├── git.rs
│   │       ├── llm.rs
│   │       ├── generator.rs
│   │       ├── templates.rs
│   │       ├── exporters.rs
│   │       ├── watch.rs    # 后台监听 worker
│   │       └── ...
│   └── cli/                # CLI binary
├── src-tauri/              # Tauri Rust 主进程（独立 cargo 项目）
│   ├── src/
│   │   ├── main.rs
│   │   ├── state.rs
│   │   ├── commands.rs     # 21 个 #[tauri::command]
│   │   └── tray.rs
│   ├── tauri.conf.json
│   └── icons/
├── src/                    # 前端 React
│   ├── api/
│   │   ├── ipc.ts
│   │   └── types.ts
│   ├── components/
│   ├── hooks/
│   ├── pages/
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

## 数据位置

- 配置：`~/.report-assistant/config.yml`
- 数据库：`~/.report-assistant/data.sqlite`（WAL 模式）
- 截图：`~/.report-assistant/screenshots/`（默认分析后即删）
- 日志：`~/.report-assistant/logs/app.log`（按天轮转）

## 与旧版 (PySide6) 的差别

| 项 | 旧（Python + PySide6） | 新（Rust + Tauri） |
|---|---|---|
| 启动 | 5–10 秒（onefile 解压） | 瞬开 |
| 体积 | 75 MB | 18 MB（GUI）+ 9 MB（CLI） |
| UI 卡顿 | WatchWorker 持 GIL 卡 UI | 完全多线程隔离 |
| 数据库 | rollback journal 排他锁 | WAL 读写并发 |
| 内存占用 | ~150 MB | ~50 MB |

数据库 schema 完全兼容，旧 sqlite 文件可直接复用。

## License

MIT
