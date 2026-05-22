<div align="center">
  <img src="src-tauri/icons/icon.png" width="120" alt="小T日报助手" style="image-rendering: pixelated" />
  <h1>小T日报助手</h1>
  <p><strong>AI 驱动的工作日报 / 周报 / 月报生成工具</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Rust-1.94+-CE422B?logo=rust&logoColor=white" />
    <img src="https://img.shields.io/badge/Tauri-v2-24C8DB?logo=tauri&logoColor=white" />
    <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" />
    <img src="https://img.shields.io/badge/license-MIT-7BC47F" />
  </p>
  <p>
    像素风界面 · 清新绿主题 · 启动瞬开 · UI 永不卡顿
  </p>
</div>

---

## ✨ 这是什么

一个跑在你本机的小工具：定时给屏幕拍照、扫你电脑上的 git 仓库，让 AI 顺带把一天/一周/一月做了什么写成日报。所有数据都只在本地，截图分析完默认即删。

灵感来自 [小黑日报助手](https://xiaohei.qitingai.com/) 的"截图记录 + AI 总结"路子，加上对研发更友好的 **Git 提交识别**、**多显示器**、**空闲检测**。

## 🎯 特性

- 🖥️ **截图工作流**：定时截屏 → 视觉模型识别工作类别 → 入库
- 🌿 **Git 提交收集**：扫多仓库，按邮箱/姓名识别"我的"提交
- 📝 **报告生成**：日报 / 周报 / 月报，4 种模板（standard / concise / technical / okr）
- 📤 **导出格式**：Markdown / HTML / TXT / **Word (docx)**
- 🔒 **隐私优先**：截图分析后默认即删；数据全在本地 SQLite
- 🖥️ **多显示器**：可选择监控的屏幕
- 🌙 **空闲跳过**：用户离开时不浪费 token
- 🎨 **像素风 UI** + 清新绿主题 + 自定义标题栏
- 🚀 **轻量**：GUI 安装包仅 5.5MB（NSIS）

## 📥 安装

下载 [Releases](https://github.com/ethanfly/report-assistant/releases) 中对应平台的安装包：

- **Windows**：`小T日报助手_X.X.X_x64-setup.exe`（NSIS 安装器）
- **macOS**：`小T日报助手.app.tar.gz` 或 `.dmg`
- **Linux**：`.deb` / `.AppImage`

## ⚙️ 快速上手

1. 安装并启动应用
2. 进入 **设置 → LLM**，填入你的 API Key（OpenAI 兼容协议都行：OpenAI / DeepSeek / 通义 / 智谱 / 自建 vLLM ...）
3. 点击 **测试连接**，确认能联通
4. 进入 **设置 → Git**，点 "浏览并添加..." 选你的代码仓库目录（支持多选批量添加）
5. 回到首页，点 **开始监听** —— 之后会自动定时分析屏幕
6. 想看报告？点首页的 **生成今日日报 / 生成本周周报 / 生成本月月报**

配置文件在 `~/.report-assistant/config.yml`，也可以直接编辑。环境变量优先级最高：`REPORT_ASSISTANT_API_KEY` / `REPORT_ASSISTANT_BASE_URL` / `REPORT_ASSISTANT_MODEL`。

## 🛠️ CLI 用法

本项目还提供功能等价的命令行工具 `report-assistant`：

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
report-assistant report export <id> --format docx --out ~/Documents

# 数据查看
report-assistant logs --limit 50 --source git
report-assistant stats

# 工具
report-assistant llm test
report-assistant monitors
report-assistant cleanup --days 60
```

所有命令支持 `--json` 输出，便于脚本接入。

## 🏗️ 技术栈

- **核心**：Rust 1.94+（Cargo workspace，4 个 crate）
  - `crates/core` — 业务核心库（截图 / Git / LLM / SQLite / 报告 / 导出 / 监听）
  - `crates/cli` — 命令行（clap derive）
  - `crates/icon-gen` — 像素艺术图标生成器
  - `src-tauri` — Tauri v2 桌面壳（独立子项目）
- **前端**：React 18 + TypeScript + Tailwind CSS + Vite
- **存储**：SQLite + WAL（读写并发）
- **截图**：xcap（跨平台原生）
- **LLM**：OpenAI 兼容协议（reqwest + rustls）
- **Git**：libgit2（vendored，无需系统 git）

## 🧑‍💻 本地开发

要求：Rust stable + Node 22+ + pnpm 10+。

```bash
# 克隆 + 装依赖
git clone https://github.com/ethanfly/report-assistant.git
cd report-assistant
pnpm install

# 开发模式（vite dev server + tauri 热重载）
pnpm tauri dev

# Release 构建（产 NSIS 安装包等）
pnpm tauri build

# 单独构建 CLI
cargo build --release -p report-assistant-cli
# 产物：target/release/report-assistant(.exe)

# 重新生成图标
cargo run --release -p icon-gen
```

## 📁 项目结构

```
report-assistant/
├── Cargo.toml              # workspace 根（不含 src-tauri）
├── crates/
│   ├── core/               # 业务核心库
│   ├── cli/                # CLI binary
│   └── icon-gen/           # 一次性图标生成器
├── src-tauri/              # Tauri Rust 主进程（独立 cargo 项目）
│   ├── src/
│   │   ├── main.rs
│   │   ├── state.rs        # AppState
│   │   ├── commands.rs     # 21 个 #[tauri::command]
│   │   └── tray.rs         # 系统托盘
│   ├── capabilities/       # 窗口/对话框等权限
│   ├── tauri.conf.json
│   └── icons/
├── src/                    # 前端 React
│   ├── api/                # invoke 包装 + 类型
│   ├── components/         # Sidebar / TitleBar / DatePicker / WeekPicker / MonthPicker ...
│   ├── hooks/
│   ├── pages/              # Home / Timeline / Reports / Settings
│   └── App.tsx
├── public/
│   └── avatar.png          # 像素风头像
└── docs/
    ├── donate-wechat.png
    └── donate-alipay.jpg
```

## 📂 数据位置

所有用户数据都在 `~/.report-assistant/` 下：

- 配置：`config.yml`
- 数据库：`data.sqlite`（WAL 模式）+ `data.sqlite-wal` / `data.sqlite-shm`（伴生）
- 截图：`screenshots/`（默认分析后即删）
- 日志：`logs/app.log.YYYY-MM-DD`（按天轮转）

## 🔐 隐私

- 截图分析完默认立即删除（可在设置中改）
- 所有数据只在本地 SQLite，不上传任何服务器
- LLM 调用走你自己配的 API（OpenAI / 自建 vLLM / 任何兼容协议都行）
- Word/HTML/MD 导出都在本地

## ❤️ 打赏支持

如果这个工具帮到了你，欢迎请作者喝杯咖啡。

<table>
  <tr>
    <td align="center">
      <img src="docs/donate-wechat.png" width="240" alt="微信收款码" /><br/>
      <sub><b>微信</b></sub>
    </td>
    <td align="center">
      <img src="docs/donate-alipay.jpg" width="240" alt="支付宝收款码" /><br/>
      <sub><b>支付宝</b></sub>
    </td>
  </tr>
</table>

## 🪪 License

MIT
