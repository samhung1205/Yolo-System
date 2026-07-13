# -*- coding: utf-8 -*-
"""
Avatar helpers, DPI helpers, and URL check for desktop UI.
"""
import os
import shutil
import uuid
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFileDialog


def _ensure_qgui_app():
    """Return QGuiApplication, creating a temporary one if needed (e.g. before QApplication in __main__)."""
    app = QGuiApplication.instance()
    if app is None:
        import sys

        argv = sys.argv if getattr(sys, "argv", None) else [""]
        return QGuiApplication(argv), True
    return app, False


def get_screen_resolution():
    app, created = _ensure_qgui_app()
    try:
        screen = app.primaryScreen()
        if screen is None:
            return None
        g = screen.availableGeometry()
        return (g.width(), g.height())
    finally:
        if created:
            app.quit()


def get_windows_scaling_factor():
    app, created = _ensure_qgui_app()
    try:
        screen = app.primaryScreen()
        if screen is None:
            return None
        return float(screen.devicePixelRatio())
    finally:
        if created:
            app.quit()


def check_url(source) -> bool:
    if source is None:
        return False
    s = str(source).strip().lower()
    return s.startswith(("http://", "https://"))


def save_avatar_file(source_path: str, dest_filename: Optional[str] = None) -> Optional[str]:
    """Copy avatar into local user_avatars folder; return destination path."""
    if not source_path:
        return None
    os.makedirs("user_avatars", exist_ok=True)
    ext = os.path.splitext(source_path)[1] or ".jpg"
    name = dest_filename or f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join("user_avatars", name)
    shutil.copyfile(source_path, dest)
    return dest


def set_circular_avatar(label):
    pixmap = label.pixmap()
    if pixmap is None or pixmap.isNull():
        return

    diameter = min(label.width(), label.height())
    if diameter <= 0:
        diameter = min(pixmap.width(), pixmap.height())
    if diameter <= 0:
        return

    scaled = pixmap.scaled(
        diameter,
        diameter,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )

    circular = QPixmap(diameter, diameter)
    circular.fill(Qt.GlobalColor.transparent)

    painter = QPainter(circular)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path)
    x = (diameter - scaled.width()) // 2
    y = (diameter - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()

    label.setPixmap(circular)


def set_border_avatar(label, pixmap: QPixmap, border_width: int, border_color: QColor):
    """Draw image centered inside label with solid border padding around it."""
    w = max(label.width(), 1)
    h = max(label.height(), 1)

    inner_w = max(1, w - 2 * border_width)
    inner_h = max(1, h - 2 * border_width)

    out = QPixmap(w, h)
    out.fill(border_color)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scaled = pixmap.scaled(
        inner_w,
        inner_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (w - scaled.width()) // 2
    y = (h - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()

    label.setPixmap(out)


def upload_avatar(label, circular=False, border_width=30, border_color=None):
    """Pick an image and show it on label; return file path or None."""
    bc = border_color if border_color is not None else QColor("#ffffff")

    path, _ = QFileDialog.getOpenFileName(
        label.window() if hasattr(label, "window") else None,
        "选择头像",
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)",
    )
    if not path:
        return None

    pix = QPixmap(path)
    if pix.isNull():
        return None

    lw = max(label.width(), 1)
    lh = max(label.height(), 1)

    if circular:
        scaled = pix.scaled(
            lw,
            lh,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled)
        set_circular_avatar(label)
    else:
        set_border_avatar(label, pix, border_width, bc)

    return path
