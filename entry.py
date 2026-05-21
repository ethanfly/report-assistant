"""PyInstaller 打包入口。

源码运行用 `python -m report_assistant.desktop.app` 即可；
打包成单文件 exe 时 PyInstaller 需要一个顶级脚本作为 entry，
该文件就是那个 entry。

注意：日志/异常钩子的初始化必须发生在导入任何业务模块之前，
这样即便业务模块的 import 阶段就抛异常也能被捕获到日志里。
"""
from report_assistant.logging_setup import bootstrap

# 必须最先调用：重定向 stdout/stderr + 装全局异常钩子
bootstrap()

from report_assistant.desktop.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
