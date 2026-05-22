//! 后台截图分析监听服务。
//!
//! 在独立 tokio task 中循环：
//! 1. 检查空闲时间（idle_skip_seconds），过则跳过本轮
//! 2. 截图 → 调 LLM 视觉分析 → 写入 work_logs（source=screenshot）
//! 3. 每个事件通过 [`WatchEvent`] 通过 ``tokio::sync::broadcast`` 通道广播给订阅者
//!
//! 调用方拿到 [`WatchHandle`] 后可以 ``stop()`` 优雅停止。

use std::sync::Arc;
use std::time::Duration;

use chrono::Local;
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;
use tokio::task::JoinHandle;
use tracing::{error, info, warn};

use crate::{
    config::Config,
    llm::LlmClient,
    screenshot, storage,
};

/// 截图分析时使用的视觉提示词。
pub const VISION_PROMPT: &str = "你是工作内容识别助手。请分析这张屏幕截图，识别用户当前正在做什么工作。

请用 JSON 格式返回，且仅返回 JSON，不要添加 markdown 代码块标记：
{
  \"category\": \"开发|会议|沟通|文档|学习|设计|测试|其他\",
  \"title\": \"一句话概括（10-20 字）\",
  \"summary\": \"2-3 句话描述具体在做什么、用到的工具/项目/页面\",
  \"keywords\": [\"关键词1\", \"关键词2\"]
}

注意：
- 如果截图中有明显的代码、IDE、终端，归类为\"开发\"。
- 如果是会议软件（Zoom/Teams/腾讯会议等），归类为\"会议\"。
- 不要编造看不到的内容；信息不足就如实写\"屏幕内容不明确\"。
- 不要包含个人隐私信息（如完整邮箱、密码、token）。
";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum WatchEvent {
    /// 监听已启动
    Started { interval_seconds: u64 },
    /// 一次截图分析成功入库
    Captured {
        ts: chrono::DateTime<chrono::Local>,
        category: String,
        title: String,
        summary: String,
        keywords: Vec<String>,
    },
    /// 单次失败（不停止循环）
    Failed { message: String },
    /// 检测到空闲，跳过本轮
    IdleSkipped { idle_seconds: u64 },
    /// 监听已停止
    Stopped,
}

#[derive(Clone)]
pub struct WatchHandle {
    inner: Arc<Inner>,
}

struct Inner {
    stop_flag: Arc<std::sync::atomic::AtomicBool>,
    sender: broadcast::Sender<WatchEvent>,
    join: Mutex<Option<JoinHandle<()>>>,
}

impl WatchHandle {
    /// 订阅事件流。新订阅者只能拿到此后的事件。
    pub fn subscribe(&self) -> broadcast::Receiver<WatchEvent> {
        self.inner.sender.subscribe()
    }

    /// 请求停止。返回 future await 可等待真实退出。
    pub fn stop(&self) {
        self.inner
            .stop_flag
            .store(true, std::sync::atomic::Ordering::SeqCst);
    }

    /// 是否仍在运行。
    pub fn is_running(&self) -> bool {
        !self.inner
            .stop_flag
            .load(std::sync::atomic::Ordering::SeqCst)
    }

    /// 等待 worker task 真正结束。
    pub async fn join(&self) {
        let join = self.inner.join.lock().take();
        if let Some(j) = join {
            let _ = j.await;
        }
    }
}

/// 启动后台监听 worker，立即返回 [`WatchHandle`]。
///
/// LLM 客户端按 cfg.llm 构造一次复用；连续失败不会停止循环，但会通过
/// [`WatchEvent::Failed`] 通知订阅者。
pub fn start(cfg: Config, storage_db: storage::Storage) -> WatchHandle {
    let (tx, _rx) = broadcast::channel::<WatchEvent>(64);
    let stop_flag = Arc::new(std::sync::atomic::AtomicBool::new(false));

    let cfg_arc = Arc::new(cfg);
    let interval = cfg_arc.screenshot.interval_seconds.max(10);

    let tx_clone = tx.clone();
    let stop_clone = stop_flag.clone();

    let task = tokio::spawn(async move {
        run_loop(cfg_arc, storage_db, tx_clone, stop_clone, interval).await;
    });

    let inner = Inner {
        stop_flag,
        sender: tx,
        join: Mutex::new(Some(task)),
    };
    WatchHandle { inner: Arc::new(inner) }
}

async fn run_loop(
    cfg: Arc<Config>,
    storage_db: storage::Storage,
    tx: broadcast::Sender<WatchEvent>,
    stop: Arc<std::sync::atomic::AtomicBool>,
    interval: u64,
) {
    // 构造 LLM 客户端：监听必须有"默认视觉模型"
    let vision_provider = match cfg.llm.resolve_vision() {
        Some(p) => p.clone(),
        None => {
            let msg = "未配置默认视觉模型，无法启动监听。请在设置 → LLM 中先添加并指定一个视觉 provider。";
            error!("{}", msg);
            let _ = tx.send(WatchEvent::Failed {
                message: msg.to_string(),
            });
            let _ = tx.send(WatchEvent::Stopped);
            return;
        }
    };
    let llm = match LlmClient::new(vision_provider) {
        Ok(c) => c,
        Err(e) => {
            error!("WatchWorker LLM 初始化失败: {}", e);
            let _ = tx.send(WatchEvent::Failed {
                message: format!("LLM 初始化失败: {}", e),
            });
            let _ = tx.send(WatchEvent::Stopped);
            return;
        }
    };

    let _ = tx.send(WatchEvent::Started {
        interval_seconds: interval,
    });
    info!(interval, "WatchWorker 启动");

    let screenshot_dir = match cfg.resolved_screenshot_dir() {
        Ok(d) => d,
        Err(e) => {
            let _ = tx.send(WatchEvent::Failed {
                message: format!("截图目录不可用: {}", e),
            });
            let _ = tx.send(WatchEvent::Stopped);
            return;
        }
    };

    let idle_threshold = cfg.screenshot.idle_skip_seconds;
    let monitor_index = cfg.screenshot.monitor_index;
    let keep = cfg.screenshot.keep_after_analysis;

    while !stop.load(std::sync::atomic::Ordering::SeqCst) {
        // 空闲检测
        if idle_threshold > 0 {
            let idle = screenshot::idle_seconds();
            if idle >= idle_threshold {
                let _ = tx.send(WatchEvent::IdleSkipped { idle_seconds: idle });
                sleep_interruptible(interval.min(60), &stop).await;
                continue;
            }
        }

        // 截图（同步耗时操作，丢到 blocking thread）
        let dir = screenshot_dir.clone();
        let shot = tokio::task::spawn_blocking(move || {
            screenshot::capture_screen(dir, monitor_index)
        })
        .await;
        let path = match shot {
            Ok(Ok(p)) => p,
            Ok(Err(e)) => {
                warn!("截图失败: {}", e);
                let _ = tx.send(WatchEvent::Failed {
                    message: format!("截图失败: {}", e),
                });
                sleep_interruptible(interval, &stop).await;
                continue;
            }
            Err(e) => {
                warn!("截图任务 panic: {}", e);
                let _ = tx.send(WatchEvent::Failed {
                    message: format!("截图任务异常: {}", e),
                });
                sleep_interruptible(interval, &stop).await;
                continue;
            }
        };

        // 视觉分析（异步 IO）
        let analyze_result = llm.analyze_image(&path, VISION_PROMPT).await;

        // 处理图片：分析失败或不保留时删除
        let parsed_ok = matches!(analyze_result, Ok(_));
        if !keep || !parsed_ok {
            let _ = std::fs::remove_file(&path);
        }

        let raw = match analyze_result {
            Ok(s) => s,
            Err(e) => {
                warn!("视觉分析失败: {}", e);
                let _ = tx.send(WatchEvent::Failed {
                    message: format!("视觉分析失败: {}", e),
                });
                sleep_interruptible(interval, &stop).await;
                continue;
            }
        };

        let parsed = parse_vision_json(&raw);
        let now = Local::now();

        // 入库
        let meta = serde_json::json!({
            "keywords": parsed.keywords,
            "image_path": if keep { path.to_string_lossy().to_string() } else { String::new() },
        });
        if let Err(e) = storage_db.add_work_log(
            now,
            "screenshot",
            &parsed.title,
            &parsed.summary,
            Some(&parsed.category),
            meta,
            None,
        ) {
            warn!("入库失败: {}", e);
            let _ = tx.send(WatchEvent::Failed {
                message: format!("入库失败: {}", e),
            });
        } else {
            let _ = tx.send(WatchEvent::Captured {
                ts: now,
                category: parsed.category,
                title: parsed.title,
                summary: parsed.summary,
                keywords: parsed.keywords,
            });
        }

        sleep_interruptible(interval, &stop).await;
    }

    info!("WatchWorker 退出");
    let _ = tx.send(WatchEvent::Stopped);
}

async fn sleep_interruptible(seconds: u64, stop: &Arc<std::sync::atomic::AtomicBool>) {
    let mut left = seconds;
    while left > 0 && !stop.load(std::sync::atomic::Ordering::SeqCst) {
        tokio::time::sleep(Duration::from_secs(1)).await;
        left -= 1;
    }
}

struct ParsedVision {
    category: String,
    title: String,
    summary: String,
    keywords: Vec<String>,
}

fn parse_vision_json(text: &str) -> ParsedVision {
    let mut s = text.trim().to_string();
    // 去掉 ```json ... ``` 包裹
    if s.starts_with("```") {
        let lines: Vec<&str> = s.lines().collect();
        let body: Vec<&str> = lines
            .iter()
            .skip_while(|l| l.starts_with("```"))
            .take_while(|l| l.trim() != "```")
            .copied()
            .collect();
        s = body.join("\n").trim().to_string();
    }
    // 截取首个 { 到最后一个 }
    if !s.starts_with('{') {
        if let (Some(i), Some(j)) = (s.find('{'), s.rfind('}')) {
            if j > i {
                s = s[i..=j].to_string();
            }
        }
    }

    match serde_json::from_str::<serde_json::Value>(&s) {
        Ok(v) => {
            let category = v
                .get("category")
                .and_then(|x| x.as_str())
                .unwrap_or("其他")
                .to_string();
            let title = v
                .get("title")
                .and_then(|x| x.as_str())
                .unwrap_or("屏幕内容")
                .chars()
                .take(60)
                .collect();
            let summary = v
                .get("summary")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .chars()
                .take(500)
                .collect();
            let keywords = v
                .get("keywords")
                .and_then(|x| x.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .take(10)
                        .collect()
                })
                .unwrap_or_default();
            ParsedVision { category, title, summary, keywords }
        }
        Err(_) => ParsedVision {
            category: "其他".to_string(),
            title: text.trim().chars().take(30).collect(),
            summary: text.trim().chars().take(300).collect(),
            keywords: vec![],
        },
    }
}
