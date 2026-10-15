import sys
sys.path.insert(0, "/Users/gabrielsk/Desktop/REKORDBOX_EXTRACTOR")
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
import app_logging
app = QApplication([])
app_logging.install_excepthook()
class Boom(QThread):
    def run(self):
        raise PermissionError("Permission denied: '/Volumes/MUSIC'")
t = Boom(); t.start()
def close_modal():
    w = QApplication.activeModalWidget()
    print("modal shown:", w is not None, flush=True)
    if w: w.done(0)
    QTimer.singleShot(200, app.quit)
QTimer.singleShot(1500, close_modal)
app.exec(); t.wait(2000); print("alive", flush=True)
