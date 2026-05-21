"""PyInstaller 打包入口。

源码运行用 `python -m report_assistant.desktop.app` 即可；
打包成单文件 exe 时 PyInstaller 需要一个顶级脚本作为 entry，
该文件就是那个 entry。
"""
from report_assistant.desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
