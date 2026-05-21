"""自定义数字输入控件。

替代 QSpinBox：QSS 方式自定义 up/down 按钮在 Qt 6 Windows 平台
经常出现 hit-test 区域错乱（点哪边都识别为 up），改用三段式手搭：
[QLineEdit | minus 按钮 | plus 按钮]，每个按钮是独立 QToolButton，
点击区域绝对清晰。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QIntValidator
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QToolButton, QSizePolicy,
)

from ..assets import icon_path


class NumberInput(QFrame):
    """整数输入框 + 加减按钮。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 10_000,
        value: int = 0,
        suffix: str = "",
        special_value_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("NumberInput")
        self._min = minimum
        self._max = maximum
        self._suffix = suffix
        self._special_value_text = special_value_text
        self._value = max(minimum, min(maximum, value))
        self._suppress_change = False

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.edit = QLineEdit()
        self.edit.setObjectName("NumberInputEdit")
        self.edit.setValidator(QIntValidator(minimum, maximum, self.edit))
        self.edit.editingFinished.connect(self._on_edit_finished)
        layout.addWidget(self.edit, 1)

        self.btn_minus = QToolButton()
        self.btn_minus.setObjectName("NumberInputBtnMinus")
        self.btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minus.setAutoRepeat(True)
        self.btn_minus.setAutoRepeatDelay(400)
        self.btn_minus.setAutoRepeatInterval(80)
        self._set_icon(self.btn_minus, "minus")
        self.btn_minus.clicked.connect(self._dec)
        layout.addWidget(self.btn_minus)

        self.btn_plus = QToolButton()
        self.btn_plus.setObjectName("NumberInputBtnPlus")
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.setAutoRepeat(True)
        self.btn_plus.setAutoRepeatDelay(400)
        self.btn_plus.setAutoRepeatInterval(80)
        self._set_icon(self.btn_plus, "plus")
        self.btn_plus.clicked.connect(self._inc)
        layout.addWidget(self.btn_plus)

        self._refresh_display()

    def _set_icon(self, btn: QToolButton, name: str) -> None:
        p = icon_path(f"{name}.png")
        if p.exists():
            btn.setIcon(QIcon(str(p)))
        else:
            btn.setText("+" if name == "plus" else "−")

    def _refresh_display(self) -> None:
        self._suppress_change = True
        if self._special_value_text and self._value == self._min:
            self.edit.setText(self._special_value_text)
        else:
            self.edit.setText(
                f"{self._value}{self._suffix}" if self._suffix else str(self._value)
            )
        self._suppress_change = False
        self.btn_minus.setEnabled(self._value > self._min)
        self.btn_plus.setEnabled(self._value < self._max)

    def _on_edit_finished(self) -> None:
        if self._suppress_change:
            return
        text = self.edit.text().strip()
        if self._suffix and text.endswith(self._suffix):
            text = text[: -len(self._suffix)].strip()
        if self._special_value_text and text == self._special_value_text:
            new_val = self._min
        else:
            try:
                new_val = int(text)
            except ValueError:
                self._refresh_display()
                return
        self.setValue(new_val)

    def _inc(self) -> None:
        self.setValue(self._value + 1)

    def _dec(self) -> None:
        self.setValue(self._value - 1)

    # ── 兼容 QSpinBox 的公开 API ─────────────
    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(self._min, min(self._max, int(v)))
        if v == self._value:
            self._refresh_display()
            return
        self._value = v
        self._refresh_display()
        self.valueChanged.emit(v)

    def setRange(self, mn: int, mx: int) -> None:
        self._min = mn
        self._max = mx
        self.edit.setValidator(QIntValidator(mn, mx, self.edit))
        self.setValue(self._value)

    def setSuffix(self, suffix: str) -> None:
        self._suffix = suffix
        self._refresh_display()

    def setSpecialValueText(self, text: str) -> None:
        self._special_value_text = text
        self._refresh_display()
