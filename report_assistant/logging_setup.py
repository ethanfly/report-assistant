"""统一日志与全局异常钩子。

桌面端打包成 windowed exe 后没有控制台，任何未捕获异常都会让进程静默退出。
本模块解决三件事：

1. 日志写入用户目录下的 `~/.report-assistant/logs/app.log`，并做大小轮转。
2. 安装 ``sys.excepthook`` / ``threading.excepthook`` / ``asyncio`` 异常处理器，
   把所有未捕获异常落盘，防止进程静默死掉。
3. windowed 模式下 ``sys.stdout`` / ``sys.stderr`` 可能为 ``None``，
   ``print`` 会抛 ``RuntimeError: lost sys.stdout``。这里把它们替换成
   写日志的 file-like 对象，老代码里的 ``print`` 不再有副作用。
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from .config import DEFAULT_CONFIG_DIR


_INSTALLED = False
_LOG_DIR = DEFAULT_CONFIG_DIR / "logs"
_LOG_FILE = _LOG_DIR / "app.log"


class _LoggerWriter:
    """让 print/traceback 之类直接写到 logger 的 file-like 适配器。"""

    def __init__(self, level: int = logging.INFO, name: str = "stdout"):
        self._logger = logging.getLogger(f"redirect.{name}")
        self._level = level
        self._buf = ""

    def write(self, message: str) -> int:
        if not isinstance(message, str):
            try:
                message = message.decode("utf-8", errors="replace")  # type: ignore[attr-defined]
            except Exception:
                message = str(message)
        self._buf += message
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip()
            if line:
                self._logger.log(self._level, line)
        return len(message)

    def flush(self) -> None:
        if self._buf.strip():
            self._logger.log(self._level, self._buf.strip())
        self._buf = ""

    def isatty(self) -> bool:
        return False


def log_dir() -> Path:
    """返回日志目录路径（已确保存在）。"""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def log_file() -> Path:
    """返回主日志文件路径。"""
    log_dir()
    return _LOG_FILE


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """初始化日志系统，幂等。返回根 logger。"""
    global _INSTALLED
    root = logging.getLogger()
    if _INSTALLED:
        return root

    log_dir()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler：5MB 轮转，保留 5 份
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except OSError:
        # 写不了文件就算了，至少不要因为日志而崩
        pass

    # 控制台 handler：仅在有 stdout 时挂上（避免 windowed 模式打印到 None）
    if sys.stderr is not None:
        try:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(fmt)
            stream_handler.setLevel(level)
            root.addHandler(stream_handler)
        except Exception:
            pass

    root.setLevel(level)
    _INSTALLED = True
    return root


def redirect_std_streams() -> None:
    """把 None 的 stdout/stderr 替换成日志写入器。

    PyInstaller 用 ``console=False`` 打包时，子进程没有标准流，
    任何 ``print`` / ``traceback.print_exc`` 都会抛
    ``RuntimeError: lost sys.stdout``。
    """
    if sys.stdout is None:
        sys.stdout = _LoggerWriter(logging.INFO, "stdout")  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _LoggerWriter(logging.ERROR, "stderr")  # type: ignore[assignment]


def install_excepthooks() -> None:
    """安装全局异常钩子，未捕获异常一律落到日志。"""
    logger = logging.getLogger("excepthook")

    def _sys_hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # 保留默认行为，方便 Ctrl+C
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.error("未捕获异常", exc_info=(exc_type, exc, tb))

    sys.excepthook = _sys_hook

    # Python 3.8+ 线程异常钩子
    def _thread_hook(args: "threading.ExceptHookArgs") -> None:  # type: ignore[name-defined]
        if issubclass(args.exc_type, SystemExit):
            return
        logger.error(
            "线程未捕获异常 (thread=%s)",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    try:
        threading.excepthook = _thread_hook  # type: ignore[assignment]
    except Exception:
        pass


def bootstrap(level: int = logging.INFO) -> logging.Logger:
    """一站式初始化：重定向标准流 + 配置日志 + 装异常钩子。"""
    redirect_std_streams()
    logger = setup_logging(level)
    install_excepthooks()
    return logger


def open_log_dir() -> Optional[Path]:
    """在系统文件管理器中打开日志目录，便于用户查看。"""
    p = log_dir()
    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", str(p)])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(p)])
        return p
    except Exception:
        return p
