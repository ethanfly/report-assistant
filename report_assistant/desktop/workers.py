"""后台 worker：把耗时调用从 UI 线程剥离。

PySide6 的信号是线程安全的；用 QThread + worker 对象的标准模式。
"""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ..config import Config, LLMConfig
from ..generator import generate_report
from ..llm import LLMClient, LLMError, build_client, check_connection
from ..screenshot import analyze_and_record
from ..storage import Storage


logger = logging.getLogger("desktop.workers")


class CaptureWorker(QObject):
    """单次截图 + 视觉分析。"""

    finished = Signal(dict)        # {category, title, summary, keywords, ts}
    failed = Signal(str)

    def __init__(self, cfg: Config, storage: Storage):
        super().__init__()
        self.cfg = cfg
        self.storage = storage

    def run(self) -> None:
        try:
            with build_client(self.cfg.llm) as llm:
                shot = analyze_and_record(self.cfg, self.storage, llm)
            self.finished.emit({
                "ts": shot.ts,
                "category": shot.category,
                "title": shot.title,
                "summary": shot.summary,
                "keywords": shot.keywords,
            })
        except (LLMError, RuntimeError) as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit(traceback.format_exc())


class WatchWorker(QObject):
    """长驻：按间隔截屏分析，单条结果通过 captured 信号送出。"""

    captured = Signal(dict)        # 单次截图结果
    failed = Signal(str)            # 单次失败（不停止循环）
    idle_skipped = Signal(int)      # 空闲跳过（附带空闲秒数）
    stopped = Signal()

    def __init__(self, cfg: Config, storage: Storage, interval: int):
        super().__init__()
        self.cfg = cfg
        self.storage = storage
        self.interval = max(10, int(interval))
        self._stop = False
        self._llm: Optional[LLMClient] = None

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from ..screenshot import get_idle_seconds
        try:
            self._llm = build_client(self.cfg.llm)
        except Exception as e:
            logger.exception("LLM 初始化失败")
            self.failed.emit(f"LLM 初始化失败: {e}")
            self.stopped.emit()
            return
        logger.info("WatchWorker 启动 (interval=%ss)", self.interval)
        try:
            while not self._stop:
                # 外层 try 兜底：任何意外都不应该让循环退出。这是后台监听
                # 持久运行的关键 —— 网络抖动、磁盘临时不可写、PIL 解码失败
                # 之类全都吞掉、记日志、继续下一轮。
                try:
                    idle_threshold = int(
                        getattr(self.cfg.screenshot, "idle_skip_seconds", 0) or 0
                    )
                    if idle_threshold > 0:
                        idle = get_idle_seconds()
                        if idle >= idle_threshold:
                            self.idle_skipped.emit(idle)
                            slept = 0
                            while slept < min(self.interval, 60) and not self._stop:
                                time.sleep(1)
                                slept += 1
                            continue
                    try:
                        shot = analyze_and_record(self.cfg, self.storage, self._llm)
                        self.captured.emit({
                            "ts": shot.ts,
                            "category": shot.category,
                            "title": shot.title,
                            "summary": shot.summary,
                            "keywords": shot.keywords,
                        })
                    except (LLMError, RuntimeError) as e:
                        logger.warning("截图分析失败: %s", e)
                        self.failed.emit(str(e))
                    except Exception as e:
                        # 比如 OSError（磁盘满）、httpx.ConnectError、PIL 异常等
                        logger.exception("截图分析出现未预期异常")
                        self.failed.emit(f"{type(e).__name__}: {e}")
                except Exception:
                    # 极端兜底：连 idle 检测都炸了也别终止
                    logger.exception("WatchWorker 单轮循环异常，已忽略")
                slept = 0
                while slept < self.interval and not self._stop:
                    time.sleep(1)
                    slept += 1
        finally:
            if self._llm:
                try:
                    self._llm.close()
                except Exception:
                    logger.exception("关闭 LLM 客户端失败")
            logger.info("WatchWorker 退出")
            self.stopped.emit()


class ReportWorker(QObject):
    """生成报告。"""

    finished = Signal(dict)        # generate_report 的返回结构
    failed = Signal(str)

    def __init__(
        self,
        cfg: Config,
        storage: Storage,
        kind: str,
        anchor: Optional[datetime],
        template: Optional[str],
        notes: str,
    ):
        super().__init__()
        self.cfg = cfg
        self.storage = storage
        self.kind = kind
        self.anchor = anchor
        self.template = template
        self.notes = notes

    def run(self) -> None:
        try:
            with build_client(self.cfg.llm) as llm:
                result = generate_report(
                    self.cfg, self.storage, llm,
                    kind=self.kind,
                    anchor=self.anchor,
                    template=self.template,
                    extra_notes=self.notes,
                )
            self.finished.emit(result)
        except LLMError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit(traceback.format_exc())


class TestConnectionWorker(QObject):
    """LLM 连通性测试。"""

    finished = Signal(bool, str)  # (ok, message)

    def __init__(self, llm_cfg: LLMConfig):
        super().__init__()
        self.llm_cfg = llm_cfg

    def run(self) -> None:
        ok, msg = check_connection(self.llm_cfg)
        self.finished.emit(ok, msg)


class GitSyncWorker(QObject):
    """异步 Git 同步：扫描所有仓库 → 入库；放在 worker 线程避免阻塞 UI。"""

    finished = Signal(int)  # 同步到的提交条数
    failed = Signal(str)

    def __init__(self, cfg: Config, storage: Storage):
        super().__init__()
        self.cfg = cfg
        self.storage = storage

    def run(self) -> None:
        from datetime import datetime
        from ..generator import collect_data
        try:
            _, _, commits, _ = collect_data(
                self.cfg, self.storage, "daily", anchor=datetime.now(),
                include_screenshots=False,
            )
            self.finished.emit(len(commits))
        except Exception as e:
            self.failed.emit(str(e))


def start_in_thread(parent: QObject, worker: QObject) -> QThread:
    """通用工具：把 worker.run() 跑到一个新线程里。

    要点：worker 不能被 Python GC 回收（否则槽函数永远不会触发），所以
    把它挂到 parent 的列表里持有强引用，等线程 finished 时再清掉。
    """
    thread = QThread(parent)
    worker.moveToThread(thread)

    # 强引用，防 GC
    if not hasattr(parent, "_active_workers"):
        parent._active_workers = []  # type: ignore[attr-defined]
    parent._active_workers.append(worker)  # type: ignore[attr-defined]

    def _cleanup():
        try:
            parent._active_workers.remove(worker)  # type: ignore[attr-defined]
        except (ValueError, AttributeError):
            pass

    def _safe_run():
        """包一层兜底：worker.run 若抛异常应记日志而不是让线程静默死。"""
        try:
            worker.run()
        except Exception:
            logger.exception(
                "worker %s.run() 抛出未捕获异常", type(worker).__name__,
            )
            # 尽量发个失败信号，让 UI 能解锁
            failed = getattr(worker, "failed", None)
            if failed is not None:
                try:
                    failed.emit("内部错误，详见日志")
                except Exception:
                    pass
            stopped = getattr(worker, "stopped", None)
            if stopped is not None:
                try:
                    stopped.emit()
                except Exception:
                    pass

    thread.started.connect(_safe_run)
    for sig_name in ("finished", "failed", "stopped"):
        sig = getattr(worker, sig_name, None)
        if sig is not None:
            sig.connect(thread.quit)
    thread.finished.connect(_cleanup)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
