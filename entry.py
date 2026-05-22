"""PyInstaller 打包入口。

源码运行用 `python -m report_assistant.desktop.app` 即可；
打包成单文件 exe 时 PyInstaller 需要一个顶级脚本作为 entry，
该文件就是那个 entry。

注意：日志/异常钩子的初始化必须发生在导入任何业务模块之前，
这样即便业务模块的 import 阶段就抛异常也能被捕获到日志里。
"""
import time
import sys

_T0 = time.perf_counter()

def _stamp(msg: str) -> None:
    """早期阶段在日志还没起来时直接打 stderr，console 版本能看到。"""
    elapsed = time.perf_counter() - _T0
    line = f"[boot {elapsed:6.2f}s] {msg}"
    if sys.stderr is not None:
        try:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
        except Exception:
            pass

_stamp("entry.py 开始")

from report_assistant.logging_setup import bootstrap
_stamp("logging_setup 已 import")

# 必须最先调用：重定向 stdout/stderr + 装全局异常钩子
bootstrap()
_stamp("bootstrap 完成")

import logging  # noqa: E402
_boot = logging.getLogger("boot")
_boot.info("entry.py 启动用时 %.2fs", time.perf_counter() - _T0)

_stamp("准备 import desktop.app")
from report_assistant.desktop.app import main  # noqa: E402
_stamp("desktop.app 已 import")
_boot.info("desktop.app 已 import 用时 %.2fs", time.perf_counter() - _T0)

if __name__ == "__main__":
    _stamp("调用 main()")
    raise SystemExit(main())
