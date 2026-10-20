"""Application entry point."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from .. import config, paths
from ..paths import APP_ID, APP_NAME, VERSION
from .theme import apply_theme
from .window import MainWindow


def _fit_to_screen(app: QApplication, window: QWidget) -> None:
    """Keep the default window inside the usable desktop, including HiDPI."""
    screen = app.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    width = min(1280, max(window.minimumWidth(), available.width() - 32))
    height = min(860, max(window.minimumHeight(), available.height() - 40))
    window.resize(width, height)
    frame = window.frameGeometry()
    frame.moveCenter(available.center())
    window.move(frame.topLeft())


def _setup_logging() -> None:
    paths.ensure_dirs()
    handler = RotatingFileHandler(paths.log_file(), maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def run() -> int:
    _setup_logging()
    logging.getLogger(__name__).info("Bonfire %s starting", VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("Bonfire")
    app.setDesktopFileName("bonfire")
    app.setOrganizationName(APP_ID)
    apply_theme(app)

    # One scheduler per vault: two windows would race each other's rotation.
    lock = QLockFile(str(paths.data_dir() / "bonfire.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(150):
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle("Bonfire is already running")
        box.setText("Another Bonfire window is already managing this vault.")
        box.setInformativeText("Use that window to take your snapshot.")
        box.exec()
        return 0

    settings = config.load()
    window = MainWindow(settings)
    _fit_to_screen(app, window)
    window.show()
    return app.exec()
