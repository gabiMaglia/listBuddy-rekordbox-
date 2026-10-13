import faulthandler, sys, tempfile, pathlib, os, time
faulthandler.enable(); faulthandler.dump_traceback_later(80, exit=True)
sys.path.insert(0, "/Users/gabrielsk/Desktop/REKORDBOX_EXTRACTOR")
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
import styles, ui
V=os.environ.get('V','')
app = QApplication([]); styles.register_fonts(); styles.apply_theme(app, "dark")
ui.MainWindow._start_update_check = lambda self: None
tmp = pathlib.Path(tempfile.mkdtemp()) / "s.ini"
w = ui.MainWindow(settings_path=tmp)
w.resize(1300, 800); w.show(); app.processEvents()
def pump(ms):
    end=time.time()+ms/1000
    while time.time()<end: app.processEvents(); QTest.qWait(5)
def click(btn):
    if 'direct' in V: btn.click()
    else: QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
N=int(sys.argv[1])
ms=int(os.environ.get('MS','100'))
for i in range(N):
    for b in (w._src_tk_btn, w._src_rb_btn):
        click(b); pump(ms)
    print(i, flush=True)
