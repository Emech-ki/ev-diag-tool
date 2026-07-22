"""动画工具：淡入上滑揭示 + 悬浮脉冲"""

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect


def fade_slide_in(widget: QWidget, duration: int = 350, start_offset: int = 24):
    """
    淡入 + 上滑动画
    """
    opacity_effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(opacity_effect)

    pos_anim = QPropertyAnimation(widget, b"pos")
    pos_anim.setDuration(duration)
    pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    start_pos = widget.pos() + QPoint(0, start_offset)
    end_pos = widget.pos()
    pos_anim.setStartValue(start_pos)
    pos_anim.setEndValue(end_pos)

    opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
    opacity_anim.setDuration(duration)
    opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    opacity_anim.setStartValue(0.0)
    opacity_anim.setEndValue(1.0)

    from PyQt6.QtCore import QParallelAnimationGroup
    group = QParallelAnimationGroup()
    group.addAnimation(pos_anim)
    group.addAnimation(opacity_anim)
    group.start()


def start_pulse(widget: QWidget, interval_ms: int = 1200):
    """
    缓慢脉冲呼吸效果（用于状态指示器）
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(interval_ms)
    anim.setEasingCurve(QEasingCurve.Type.InOutSine)
    anim.setLoopCount(-1)
    anim.setKeyValueAt(0.0, 1.0)
    anim.setKeyValueAt(0.3, 0.4)
    anim.setKeyValueAt(0.6, 1.0)
    anim.setKeyValueAt(0.8, 0.6)
    anim.setKeyValueAt(1.0, 1.0)
    anim.start()
    return anim
