import faulthandler, sys, os, time
faulthandler.enable(); faulthandler.dump_traceback_later(80, exit=True)
sys.path.insert(0, "/Users/gabrielsk/Desktop/REKORDBOX_EXTRACTOR")
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtTest import QTest
import styles
from ui_components import PlaylistCard, PlaylistGroup
V=os.environ.get('V','')
app = QApplication([]); styles.register_fonts(); styles.apply_theme(app, "dark")
win = QWidget(); lo = QVBoxLayout(win); lo.addStretch(1); win.resize(400,600); win.show()
cards=[]; groups=[]
class Plain(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self); l.addWidget(QLabel(name)); self.holder = QWidget(); l.addWidget(self.holder)
def build(n=30):
    if 'plain' in V:
        for i in range(n):
            c = Plain(f"p{i}"); cards.append(c); lo.insertWidget(lo.count()-1, c)
        return
    for i in range(n):
        if 'group' in V and i % 5 == 0:
            g = PlaylistGroup(f"G{i}"); groups.append(g); lo.insertWidget(lo.count()-1, g)
            for j in range(3):
                c = PlaylistCard(SimpleNamespace(Name=f"p{i}{j}"), 0 if j==0 and 'empty' in V else 5, index=j); cards.append(c); g.add_card(c)
        else:
            c = PlaylistCard(SimpleNamespace(Name=f"p{i}"), 5, index=i); cards.append(c); lo.insertWidget(lo.count()-1, c)
def clear():
    cards.clear(); groups.clear()
    if 'take' in V:
        while lo.count() > 1:
            it = lo.takeAt(0); w = it.widget()
            if w: w.setParent(None)
        return
    if 'noitem' in V:
        for i in reversed(range(lo.count())):
            w = lo.itemAt(i).widget()
            if w: w.setParent(None)
        return
    if 'rm' in V:
        for i in reversed(range(lo.count())):
            it = lo.itemAt(i); w = it.widget() if it else None
            if w: lo.removeWidget(w); w.deleteLater()
        return
    if 'rmstretch' in V:
        pass
    if 'later' in V:
        while lo.count() > 1:
            it = lo.takeAt(0); w = it.widget()
            if w: w.deleteLater()
        return
    for i in reversed(range(lo.count())):
        it = lo.itemAt(i); w = it.widget() if it else None
        if w: w.setParent(None)
for it in range(int(sys.argv[1])):
    build(); 
    if 'pump' in V: QTest.qWait(30)
    clear()
    if 'pump' in V: QTest.qWait(30)
    if it % 20 == 0: print(it, flush=True)
print("done")
