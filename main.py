"""Miku 屏幕翻译 - 入口。

用法:
    python main.py
"""
import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import load_config
from app.main_window import MainWindow
from app.paths import asset_path


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Miku屏幕翻译")
    app.setWindowIcon(QIcon(str(asset_path("miku.png"))))

    cfg = load_config()
    win = MainWindow(cfg)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
