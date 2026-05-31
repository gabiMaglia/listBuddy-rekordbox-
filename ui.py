"""
ui.py
-----
Ventana principal — PyQt6.
Árbol de playlists con soporte de carpetas y checkboxes tri-estado.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db import get_playlist_tree, open_database, playlist_song_count
from worker import ExportWorker

_DARK_THEME = """
QWidget { background:#1e1e24; color:#e6e6ea; font-size:13px; }
QLineEdit, QPlainTextEdit, QTreeWidget {
    background:#15151a; border:1px solid #33333d; border-radius:6px; padding:6px;
}
QPushButton {
    background:#2d6cdf; border:none; border-radius:6px; padding:7px 14px; color:white;
}
QPushButton:hover { background:#3b7bf0; }
QPushButton:disabled { background:#3a3a44; color:#888; }
QProgressBar {
    background:#15151a; border:1px solid #33333d; border-radius:6px;
    text-align:center; height:20px;
}
QProgressBar::chunk { background:#2d6cdf; border-radius:5px; }
QTreeWidget::item { padding:4px; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RB Exporter")
        self.resize(680, 600)

        self._db = None
        self._worker: ExportWorker | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # --- Carpeta de destino ---
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Carpeta de destino:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Elegí dónde exportar…")
        folder_row.addWidget(self.folder_edit, 1)
        browse_btn = QPushButton("Elegir…")
        browse_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # --- Árbol de playlists ---
        head = QHBoxLayout()
        head.addWidget(QLabel("Playlists:"))
        head.addStretch(1)
        self.all_btn = QPushButton("Marcar todas")
        self.all_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        self.none_btn = QPushButton("Desmarcar")
        self.none_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        head.addWidget(self.all_btn)
        head.addWidget(self.none_btn)
        layout.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        # --- Exportar + progreso ---
        self.export_btn = QPushButton("Exportar seleccionadas")
        self.export_btn.clicked.connect(self._start_export)
        layout.addWidget(self.export_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        layout.addWidget(self.log_view)

        self.setCentralWidget(central)
        self.setStyleSheet(_DARK_THEME)
        self._load_playlists()

    # --------------------------------------------------------------------- #
    def _load_playlists(self) -> None:
        try:
            self._db = open_database()
            tree = get_playlist_tree(self._db)
        except RuntimeError as e:
            QMessageBox.critical(self, "Error al abrir Rekordbox", str(e))
            return

        self.tree.blockSignals(True)
        self.tree.clear()

        def add_node(node: dict, parent_item: QTreeWidgetItem) -> None:
            pl = node["playlist"]
            count = playlist_song_count(pl) if pl.is_playlist else 0
            label = f"{pl.Name}  ({count})" if pl.is_playlist else pl.Name
            item = QTreeWidgetItem(parent_item, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, pl)

            flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if pl.is_folder:
                # ItemIsAutoTristate: Qt actualiza el estado del padre
                # automáticamente cuando cambian los hijos.
                flags |= Qt.ItemFlag.ItemIsAutoTristate
            item.setFlags(flags)
            item.setCheckState(0, Qt.CheckState.Unchecked)

            for child in node["children"]:
                add_node(child, item)

        root = self.tree.invisibleRootItem()
        for node in tree:
            add_node(node, root)

        self.tree.expandAll()
        self.tree.blockSignals(False)

        # Contar solo playlists (no carpetas) para el mensaje.
        total = sum(
            1 for node in tree if node["playlist"].is_playlist
        ) + sum(
            1 for node in tree
            for child in node["children"]
            if child["playlist"].is_playlist
        )
        self._log(f"🎵 {total} playlist(s) cargada(s).")

    # --------------------------------------------------------------------- #
    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Cuando se hace click en una carpeta con estado Checked o Unchecked,
        propaga ese estado a todos sus hijos.
        PartiallyChecked lo maneja Qt automáticamente (ItemIsAutoTristate).
        """
        pl = item.data(0, Qt.ItemDataRole.UserRole)
        if not (pl and pl.is_folder):
            return
        state = item.checkState(0)
        if state == Qt.CheckState.PartiallyChecked:
            return  # Qt lo puso automáticamente; no propagar hacia abajo
        self.tree.blockSignals(True)
        self._set_children(item, state)
        self.tree.blockSignals(False)

    def _set_children(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._set_children(child, state)

    # --------------------------------------------------------------------- #
    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegí la carpeta de destino")
        if folder:
            self.folder_edit.setText(folder)

    def _set_all(self, state: Qt.CheckState) -> None:
        self.tree.blockSignals(True)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, state)
            self._set_children(item, state)
        self.tree.blockSignals(False)

    def _selected_playlists(self) -> list:
        out: list = []

        def collect(item: QTreeWidgetItem) -> None:
            pl = item.data(0, Qt.ItemDataRole.UserRole)
            if pl and pl.is_playlist and item.checkState(0) == Qt.CheckState.Checked:
                out.append(pl)
            for i in range(item.childCount()):
                collect(item.child(i))

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            collect(root.child(i))
        return out

    # --------------------------------------------------------------------- #
    def _start_export(self) -> None:
        output = self.folder_edit.text().strip()
        if not output:
            QMessageBox.warning(self, "Falta carpeta", "Elegí primero una carpeta de destino.")
            return
        selected = self._selected_playlists()
        if not selected:
            QMessageBox.warning(self, "Sin selección", "Marcá al menos una playlist.")
            return

        self.export_btn.setEnabled(False)
        self.log_view.clear()
        self._log(f"📁 Destino: {output}")

        self._worker = ExportWorker(selected, Path(output))
        self._worker.log.connect(self._log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _on_finished(self, copied: int, missing: int) -> None:
        self.export_btn.setEnabled(True)
        self._log(f"\n✅ Listo. {copied} copiadas, {missing} no encontradas.")
        QMessageBox.information(
            self,
            "Exportación terminada",
            f"Copiadas: {copied}\nNo encontradas: {missing}",
        )

    def _log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
