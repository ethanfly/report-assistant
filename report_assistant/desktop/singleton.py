"""单例守卫：基于 QLocalServer/QLocalSocket 的进程互斥。

第一个实例：监听一个命名 pipe（Win）/ unix socket（Linux/macOS）。
后续实例：连接到 server，发送 "show" 后立即退出；server 端收到后激活已有窗口。

这种方式比文件锁更可靠：
- 进程崩溃后操作系统自动释放命名端点
- 跨平台（Qt 抽象了底层实现）
- 自带 IPC 通道，方便后续传递参数
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


DEFAULT_KEY = "report-assistant.singleton"
_HANDSHAKE = b"show\n"


class SingleInstance(QObject):
    """单例守卫。

    用法::

        guard = SingleInstance()
        if guard.try_acquire(on_second_instance=lambda: win.activate()):
            # 我是首个实例，正常启动
            ...
        else:
            # 已有实例，guard 已发送激活请求并应直接退出
            sys.exit(0)
    """

    second_instance_started = Signal()  # 收到后续实例的握手

    def __init__(self, key: str = DEFAULT_KEY, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.key = key
        self._server: Optional[QLocalServer] = None

    # ── 主入口 ─────────────────────────────────────
    def try_acquire(self, on_second_instance: Optional[Callable[[], None]] = None) -> bool:
        """尝试获取单例锁。

        - 返回 True：当前进程是首个实例，应继续启动 UI。
        - 返回 False：已有实例在跑，本进程已发出激活请求，应立即退出。
        """
        # 1. 先尝试连接已有 server
        socket = QLocalSocket()
        socket.connectToServer(self.key)
        if socket.waitForConnected(500):
            socket.write(_HANDSHAKE)
            socket.flush()
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return False

        # 2. 没有现存实例 → 占位。先清理可能残留的旧端点（崩溃遗留）
        QLocalServer.removeServer(self.key)

        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not self._server.listen(self.key):
            # 极端情况下监听失败：退化为允许多开（不阻塞用户）
            self._server = None
            return True

        if on_second_instance is not None:
            self.second_instance_started.connect(on_second_instance)
        self._server.newConnection.connect(self._on_new_connection)
        return True

    # ── server 端处理 ──────────────────────────────
    def _on_new_connection(self) -> None:
        if not self._server:
            return
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
        sock.disconnected.connect(sock.deleteLater)

    def _on_ready_read(self, sock: QLocalSocket) -> None:
        try:
            data = bytes(sock.readAll())
        except Exception:
            data = b""
        if _HANDSHAKE.strip() in data:
            self.second_instance_started.emit()
        sock.disconnectFromServer()

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
