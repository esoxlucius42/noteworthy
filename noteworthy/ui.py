from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QMenu, QSplitter, QStyledItemDelegate, QStyleOptionViewItem, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget, QCheckBox,
)

from .filters import note_matches
from .models import Group, Note, STATUSES
from .storage import Storage, StorageError

STATUS_LABELS = {"todo": "Todo", "in_progress": "In Progress", "done": "Done", "cancelled": "Cancelled"}
STATUS_SYMBOLS = {"todo": "○", "in_progress": "◐", "done": "✓", "cancelled": "×"}
STATUS_COLORS = {"todo": "#f4f7fb", "in_progress": "#8fd3ff", "done": "#8ee3a8", "cancelled": "#ff9b9b"}
STATUS_ORDER = {status: index for index, status in enumerate(STATUSES)}


def display_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y")
    except ValueError:
        return "Unknown date"


class RenameDialog(QDialog):
    def __init__(self, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename group")
        self.setMinimumSize(420, 120)
        self.name = QLineEdit(current)
        self.name.selectAll()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow("Group name", self.name)
        layout.addRow(buttons)


class NoteList(QListWidget):
    noteActivated = Signal(str)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            super().keyPressEvent(event)
            return
        super().keyPressEvent(event)


class StatusItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index) -> None:
        option = QStyleOptionViewItem(option)
        status_color = index.data(Qt.ItemDataRole.UserRole + 1)
        if status_color:
            color = QColor(status_color)
            option.palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText, color)
            option.palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, color)
        super().paint(painter, option, index)


class StatusFilterButton(QToolButton):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setText("All statuses")
        menu = QMenu(self)
        self.all_action = menu.addAction("All statuses")
        self.all_action.setCheckable(True)
        self.all_action.setChecked(True)
        menu.addSeparator()
        self.status_actions = {}
        for status in STATUSES:
            action = menu.addAction(_status_icon(STATUS_COLORS[status]), f"{STATUS_SYMBOLS[status]}  {STATUS_LABELS[status]}")
            action.setCheckable(True)
            action.setData(status)
            self.status_actions[status] = action
        self.setMenu(menu)
        self.all_action.toggled.connect(self._all_toggled)
        for action in self.status_actions.values():
            action.toggled.connect(self._status_toggled)

    def selected_statuses(self) -> set[str]:
        return {status for status, action in self.status_actions.items() if action.isChecked()}

    def _all_toggled(self, checked: bool) -> None:
        if checked:
            for action in self.status_actions.values():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)
        self._update_text()
        self.changed.emit()

    def _status_toggled(self, checked: bool) -> None:
        if checked:
            self.all_action.blockSignals(True)
            self.all_action.setChecked(False)
            self.all_action.blockSignals(False)
        elif not self.selected_statuses():
            self.all_action.blockSignals(True)
            self.all_action.setChecked(True)
            self.all_action.blockSignals(False)
        self._update_text()
        self.changed.emit()

    def _update_text(self) -> None:
        selected = self.selected_statuses()
        self.setText("All statuses" if not selected else f"{len(selected)} statuses")


def _status_icon(color_value: str) -> QIcon:
    pixmap = QPixmap(12, 12)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_value))
    painter.drawEllipse(1, 1, 10, 10)
    painter.end()
    return QIcon(pixmap)


class GroupView(QWidget):
    changed = Signal()

    def __init__(self, group: Group, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = group
        self.selected_id: str | None = None
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search notes...")
        self.titles_only = QCheckBox("Titles only")
        self.status_filter = StatusFilterButton()
        self.date_filter = QComboBox()
        for label, value in (("All dates", "all"), ("Today", "today"), ("Last 7 days", "7d"), ("Last 30 days", "30d")):
            self.date_filter.addItem(label, value)
        self.sort_filter = QComboBox()
        self.sort_filter.addItem("Oldest first", "date_asc")
        self.sort_filter.addItem("Newest first", "date_desc")
        self.sort_filter.addItem("Status order", "status")
        self.list = NoteList()
        self.list.setObjectName("noteList")
        self.list.setItemDelegate(StatusItemDelegate(self.list))
        self.list.currentItemChanged.connect(self._select_item)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Note title")
        self.body = QPlainTextEdit()
        self.body.setPlaceholderText("Write your note...")
        self.status = QComboBox()
        self.status.setObjectName("noteStatus")
        for value in STATUSES:
            self.status.addItem(f"{STATUS_SYMBOLS[value]}  {STATUS_LABELS[value]}", value)
            self.status.setItemData(self.status.count() - 1, QColor(STATUS_COLORS[value]), Qt.ItemDataRole.ForegroundRole)
        self.save_timer = None
        self._build()
        self._connect()
        self.refresh()

    def _build(self) -> None:
        search_row = QHBoxLayout()
        search_row.addWidget(self.query, 1)
        search_row.addWidget(self.titles_only)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.status_filter)
        filter_row.addWidget(self.date_filter)
        filter_row.addWidget(self.sort_filter)
        filter_row.addStretch()
        left = QWidget()
        left.setObjectName("noteListPane")
        left_layout = QVBoxLayout(left)
        left_layout.addLayout(search_row)
        left_layout.addLayout(filter_row)
        left_layout.addWidget(self.list)
        editor_header = QHBoxLayout()
        editor_header.addWidget(QLabel("NOTE DETAILS"))
        editor_header.addStretch()
        editor_header.addWidget(self.status)
        right = QWidget()
        right.setObjectName("noteDetailsPane")
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(editor_header)
        right_layout.addWidget(self.title)
        right_layout.addWidget(self.body, 1)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([360, 700])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _connect(self) -> None:
        self.query.textChanged.connect(self.refresh)
        self.titles_only.stateChanged.connect(self.refresh)
        self.status_filter.changed.connect(self.refresh)
        self.date_filter.currentIndexChanged.connect(self.refresh)
        self.sort_filter.currentIndexChanged.connect(self.refresh)
        self.title.textChanged.connect(self._edit_current)
        self.body.textChanged.connect(self._edit_current)
        self.status.currentIndexChanged.connect(self._edit_current)
        self.status.currentIndexChanged.connect(self._update_status_color)

    def refresh(self) -> None:
        selected = self.selected_id
        self.list.blockSignals(True)
        self.list.clear()
        visible_notes = [
            note for note in self.group.notes
            if note_matches(note, self.query.text(), self.titles_only.isChecked(), self.status_filter.selected_statuses(), self.date_filter.currentData())
        ]
        sort_mode = self.sort_filter.currentData()
        if sort_mode == "status":
            visible_notes.sort(key=lambda note: (STATUS_ORDER[note.status], note.created_at), reverse=False)
        else:
            visible_notes.sort(key=lambda note: note.created_at, reverse=sort_mode == "date_desc")
        for note in visible_notes:
            item = QListWidgetItem(f"{STATUS_SYMBOLS[note.status]}  {note.title}\n    {display_date(note.created_at)}  ·  {STATUS_LABELS[note.status]}")
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, STATUS_COLORS[note.status])
            item.setForeground(QColor(STATUS_COLORS[note.status]))
            self.list.addItem(item)
            if note.id == selected:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        elif not self.list.count():
            self._clear_editor()

    def _select_item(self, current: QListWidgetItem | None, previous: QListWidgetItem | None = None) -> None:
        del previous
        self.selected_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        note = self.current_note()
        if not note:
            self._clear_editor()
            return
        self.title.blockSignals(True)
        self.body.blockSignals(True)
        self.status.blockSignals(True)
        self.title.setText(note.title)
        self.body.setPlainText(note.body)
        self.status.setCurrentIndex(self.status.findData(note.status))
        self.title.blockSignals(False)
        self.body.blockSignals(False)
        self.status.blockSignals(False)
        self._update_status_color()

    def current_note(self) -> Note | None:
        return next((note for note in self.group.notes if note.id == self.selected_id), None)

    def _update_status_color(self) -> None:
        status = self.status.currentData()
        if status in STATUS_COLORS:
            self.status.setStyleSheet(f"QComboBox#noteStatus {{ color: {STATUS_COLORS[status]}; }}")

    def _clear_editor(self) -> None:
        self.selected_id = None
        self.title.clear()
        self.body.clear()
        self.status.setCurrentIndex(0)

    def _edit_current(self) -> None:
        note = self.current_note()
        if not note:
            return
        note.title = self.title.text().strip() or "Untitled note"
        note.body = self.body.toPlainText()
        note.status = self.status.currentData()
        note.touch()
        self.changed.emit()
        self.refresh()

    def create_note(self) -> None:
        note = Note("Untitled note", "")
        self.group.notes.insert(0, note)
        self.selected_id = note.id
        self.changed.emit()
        self.refresh()
        self._select_item(self.list.currentItem())

    def delete_note(self) -> None:
        note = self.current_note()
        if not note:
            return
        if QMessageBox.question(self, "Delete note", f"Delete '{note.title}'?") != QMessageBox.StandardButton.Yes:
            return
        self.group.notes = [item for item in self.group.notes if item.id != note.id]
        self.selected_id = None
        self.changed.emit()
        self.refresh()


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage) -> None:
        super().__init__()
        self.setMinimumSize(1024, 758)
        self.storage = storage
        try:
            self.groups = storage.load()
            self.load_error = None
        except StorageError as exc:
            self.groups = [Group("New Group")]
            self.load_error = str(exc)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabBarDoubleClicked.connect(self.rename_group)
        self.tabs.tabCloseRequested.connect(self.delete_group)
        self.tabs.currentChanged.connect(self._update_title)
        self.tabs.tabBar().tabMoved.connect(lambda *_: self.persist())
        self.setCentralWidget(self.tabs)
        self._build_toolbar()
        self._apply_theme()
        self._populate()
        if self.load_error:
            QMessageBox.warning(self, "Could not load notes", self.load_error)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Workspace")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        add_group = QAction("Add New Group", self)
        add_group.setShortcut(QKeySequence("Ctrl+Shift+N"))
        add_group.triggered.connect(self.create_group)
        rename = QAction("Rename Group", self)
        rename.triggered.connect(lambda: self.rename_group(self.tabs.currentIndex()))
        toolbar.addAction(add_group)
        toolbar.addAction(rename)
        toolbar.addSeparator()
        new_note = QAction("＋ New note", self)
        new_note.triggered.connect(self.create_note)
        delete_note = QAction("🗑 Delete note", self)
        delete_note.triggered.connect(self.delete_note)
        toolbar.addAction(new_note)
        toolbar.addAction(delete_note)

    def _populate(self) -> None:
        self.tabs.clear()
        for group in self.groups:
            view = GroupView(group)
            view.changed.connect(self.persist)
            self.tabs.addTab(view, group.name)
        self._update_title()

    def create_group(self) -> None:
        group = Group("New Group")
        self.groups.append(group)
        view = GroupView(group)
        view.changed.connect(self.persist)
        self.tabs.addTab(view, group.name)
        self.tabs.setCurrentWidget(view)
        self.persist()
        self.rename_group(self.tabs.currentIndex())

    def rename_group(self, index: int) -> None:
        if index < 0 or index >= len(self.groups):
            return
        dialog = RenameDialog(self.groups[index].name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.name.text().strip():
            self.groups[index].name = dialog.name.text().strip()
            self.tabs.setTabText(index, self.groups[index].name)
            self.persist()

    def create_note(self) -> None:
        view = self.tabs.currentWidget()
        if isinstance(view, GroupView):
            view.create_note()

    def delete_note(self) -> None:
        view = self.tabs.currentWidget()
        if isinstance(view, GroupView):
            view.delete_note()

    def delete_group(self, index: int) -> None:
        if len(self.groups) == 1:
            if QMessageBox.question(self, "Delete final group", "Delete this group and create a new empty group?") != QMessageBox.StandardButton.Yes:
                return
        elif QMessageBox.question(self, "Delete group", f"Delete '{self.groups[index].name}' and its notes?") != QMessageBox.StandardButton.Yes:
            return
        self.groups.pop(index)
        if not self.groups:
            self.groups.append(Group("New Group"))
        self._populate()
        self.persist()

    def persist(self) -> None:
        try:
            self.storage.save(self.groups)
        except StorageError as exc:
            QMessageBox.critical(self, "Could not save notes", str(exc))

    def _update_title(self) -> None:
        self.setWindowTitle(f"Noteworthy  /  {self.groups[self.tabs.currentIndex()].name if self.groups else 'New Group'}")

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QWidget { background: #101a2b; color: #e6edf7; font-size: 14px; }
            QMainWindow { background: #0d1727; }
            QToolBar { background: #14243b; border: 0; padding: 8px 12px; spacing: 8px; }
            QToolButton, QPushButton { background: #233957; color: #d9f0ec; border: 1px solid #3e5e7c; border-radius: 6px; padding: 7px 12px; }
            QToolButton:hover, QPushButton:hover { background: #31506f; }
            QToolButton[text="Add New Group"], QToolButton[text="Rename Group"], QToolButton[text="＋ New note"] { color: #8ee3a8; }
            QToolButton[text="🗑 Delete note"] { color: #ff9b9b; }
            QLineEdit, QPlainTextEdit, QComboBox { background: #172941; color: #f4f7fb; border: 1px solid #385775; border-radius: 5px; padding: 7px; }
            QWidget#noteListPane { background: #17304a; }
            QWidget#noteDetailsPane { background: #193650; }
            QListWidget { background: #173650; border: 1px solid #2d4966; border-radius: 6px; outline: none; }
            QListWidget::item { padding: 11px 10px; border-bottom: 1px solid #203750; }
            QListWidget::item:selected { background: #315268; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #172941; color: #a9bfd3; padding: 10px 18px; margin-right: 2px; }
            QTabBar::tab:selected { background: #315268; color: #fff4cf; }
            QCheckBox { color: #c7e8dd; spacing: 6px; }
            QSplitter::handle { background: #2b4864; }
        """)
