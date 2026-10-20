"""Main window: save status, vault table, one-click backups, restore flow."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config, detect, paths, system
from ..store import (
    KIND_AUTO,
    KIND_BOSS,
    KIND_MANUAL,
    Backup,
    Vault,
    restore_backup,
    sha256_file,
)
from .theme import PALETTE, display_font, tracking_font
from .widgets import (
    ElidedLabel,
    EmberHeader,
    Emblem,
    EmptyVault,
    KindBadgeDelegate,
    StatusChip,
    Switch,
    Toast,
)

log = logging.getLogger(__name__)

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _stamp(created: datetime, weekday: bool = False, seconds: bool = False) -> str:
    """Locale-independent English timestamp, e.g. 'Wednesday, 21 October 2026 · 07:22'."""
    local = created.astimezone()
    date = f"{local.day} {_MONTHS[local.month - 1]} {local.year}"
    if weekday:
        date = f"{_WEEKDAYS[local.weekday()]}, {date}"
    clock = local.strftime("%H:%M:%S" if seconds else "%H:%M")
    return f"{date} · {clock}"


def _eyebrow(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("Eyebrow")
    label.setFont(tracking_font(6.5, 1.6))
    return label


def _hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {PALETTE['BORDER']}; border: none;")
    return line


def _vline() -> QFrame:
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet(f"background: {PALETTE['BORDER']}; border: none;")
    return line


def _when_text(created: datetime) -> str:
    local = created.astimezone()
    today = datetime.now().astimezone().date()
    day = local.date()
    if day == today:
        return f"Today · {local:%H:%M}"
    if day == today - timedelta(days=1):
        return f"Yesterday · {local:%H:%M}"
    if day.year == today.year:
        return f"{local.day} {_MONTHS[local.month - 1][:3]} · {local:%H:%M}"
    return f"{local.day} {_MONTHS[local.month - 1][:3]} {local.year} · {local:%H:%M}"


def _age_text(mtime: float) -> str:
    seconds = max(0, time.time() - mtime)
    if seconds < 90:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h ago"
    return f"{hours // 24} d ago"


def _display_path(path: Path) -> str:
    """Show paths relative to the home directory, never leaking the user name."""
    try:
        relative = Path(path).expanduser().resolve().relative_to(Path.home().resolve())
    except (OSError, RuntimeError, ValueError):
        return str(path)
    return "~" if not relative.parts else "~/" + str(relative)


class NoticeDialog(QDialog):
    """Theme-native replacement for QMessageBox (no stock blue icon)."""

    TONES: ClassVar[dict[str, tuple[str, str]]] = {
        "info": ("NOTICE", PALETTE["GOLD_DIM"]),
        "warn": ("WARNING", PALETTE["EMBER"]),
        "error": ("ERROR", "#c56a52"),
    }

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        body: str,
        *,
        tone: str = "warn",
        ok_text: str = "OK",
        cancel_text: str | None = None,
        destructive: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setMaximumWidth(580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(11)

        eyebrow_text, accent = self.TONES.get(tone, self.TONES["warn"])
        if cancel_text:
            eyebrow_text = "PLEASE CONFIRM"
        eyebrow = QLabel(eyebrow_text)
        eyebrow.setObjectName("Eyebrow")
        eyebrow.setFont(tracking_font(6.5, 1.6))
        eyebrow.setStyleSheet(f"color: {accent};")
        layout.addWidget(eyebrow)

        heading = QLabel(title)
        heading.setFont(display_font(15, QFont.Weight.DemiBold))
        heading.setWordWrap(True)
        layout.addWidget(heading)

        message = QLabel(body)
        message.setWordWrap(True)
        message.setMinimumWidth(410)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message.setStyleSheet(f"color: {PALETTE['TEXT']}; font-size: 12px;")
        layout.addWidget(message)

        layout.addSpacing(4)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = None
        if cancel_text:
            cancel = QPushButton(cancel_text)
            cancel.setObjectName("Ghost")
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)
        ok = QPushButton(ok_text)
        ok.setObjectName("DangerSolid" if destructive else "Restore")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

        if cancel is not None:
            cancel.setDefault(True)
            cancel.setFocus()
        else:
            ok.setDefault(True)


def _notice(parent: QWidget, title: str, body: str, *, tone: str = "warn", ok_text: str = "OK") -> None:
    NoticeDialog(parent, title, body, tone=tone, ok_text=ok_text).exec()


def _confirm(parent: QWidget, title: str, body: str, ok_text: str, *, destructive: bool = False) -> bool:
    dialog = NoticeDialog(
        parent, title, body, tone="warn", ok_text=ok_text,
        cancel_text="Cancel", destructive=destructive,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted


class RestoreDialog(QDialog):
    """Confirmation with the warnings that actually matter for DS:R."""

    def __init__(self, backup: Backup, target: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Restore snapshot")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setMaximumWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(12)

        eyebrow = _eyebrow("Restore snapshot")
        layout.addWidget(eyebrow)

        title = QLabel("Turn back the clock?")
        title.setFont(display_font(16, QFont.Weight.DemiBold))
        layout.addWidget(title)

        when = QLabel(_stamp(backup.created_at, weekday=True))
        when.setStyleSheet(f"color: {PALETTE['GOLD_HI']}; font-size: 15px;")
        layout.addWidget(when)

        meta = QLabel(
            f"{backup.kind_label} snapshot · {system.human_size(backup.size)}"
            + (f" · {backup.note}" if backup.note else "")
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        warning = QFrame()
        warning.setObjectName("WarningBox")
        warn_layout = QVBoxLayout(warning)
        warn_layout.setContentsMargins(14, 12, 14, 12)
        warn_layout.setSpacing(5)
        warn_title = QLabel("BEFORE YOU RESTORE")
        warn_title.setFont(tracking_font(6.5, 1.5))
        warn_title.setStyleSheet(f"color: {PALETTE['EMBER']}; border: none;")
        warn_body = QLabel(
            "Close Dark Souls first — the game overwrites the file on exit and while it runs.\n"
            "Steam Cloud can also re-upload your current progress on launch. If Cloud is enabled "
            "for this game, disable it until you have loaded the restored save."
        )
        warn_body.setWordWrap(True)
        warn_body.setStyleSheet(f"color: {PALETTE['MUTED']}; font-size: 11px; border: none;")
        warn_layout.addWidget(warn_title)
        warn_layout.addWidget(warn_body)
        layout.addWidget(warning)

        self.safety_check = QCheckBox("Keep a safety snapshot of my current save (recommended)")
        self.safety_check.setChecked(True)
        layout.addWidget(self.safety_check)

        target_label = QLabel("This file will be replaced")
        target_label.setObjectName("Small")
        layout.addWidget(target_label)
        target_path = ElidedLabel(_display_path(target))
        target_path.setObjectName("Mono")
        layout.addWidget(target_path)

        layout.addSpacing(4)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        restore = QPushButton("Restore save")
        restore.setObjectName("Restore")
        restore.setDefault(True)
        restore.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(restore)
        layout.addLayout(buttons)

    @property
    def make_safety(self) -> bool:
        return self.safety_check.isChecked()


class MainWindow(QWidget):
    def __init__(self, settings: config.Settings) -> None:
        super().__init__()
        self.settings = settings
        self.vault = Vault()
        self.vault.cleanup_incoming()
        self.detection: detect.Detection | None = None
        self.save_file: Path | None = None
        self._source = ""
        self._selected_id: str | None = None
        self._game_running = False
        self._next_due: float | None = None
        self._loading = False
        self._last_missing_scan = 0.0

        self.setWindowTitle("Bonfire — Dark Souls: Remastered Save Vault")
        icon_path = paths.asset_path("icon.png")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1280, 860)
        self.setMinimumSize(1080, 720)

        self._build_ui()
        self.details_card.setVisible(self.height() >= 860)
        self._wire_shortcuts()

        self._load_initial_save()
        self._apply_settings_to_ui()
        self._refresh_save_card()
        self._refresh_table()
        self._poll_game(initial=True)
        self._reset_schedule()
        self._update_countdown()

        self.toast = Toast(self)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_game)
        self._poll_timer.start(4000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start(15000)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = EmberHeader()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 18, 30, 16)
        header_layout.setSpacing(16)

        header_layout.addWidget(Emblem(54), 0, Qt.AlignmentFlag.AlignVCenter)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("BONFIRE")
        title.setObjectName("H1")
        title.setFont(display_font(21, QFont.Weight.Bold))
        tagline = QLabel("DARK SOULS: REMASTERED   ·   SAVE VAULT")
        tagline.setObjectName("Tagline")
        tagline.setFont(tracking_font(6.5, 2.2))
        titles.addWidget(title)
        titles.addWidget(tagline)
        header_layout.addLayout(titles)
        header_layout.addStretch(1)

        self.game_chip = StatusChip("GAME CLOSED", "muted")
        self.save_chip = StatusChip("NO SAVE", "warn")
        header_layout.addWidget(self.save_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.game_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 18, 28, 12)
        body_layout.setSpacing(14)
        root.addWidget(body, 1)

        body_layout.addWidget(self._build_save_card())

        main_row = QHBoxLayout()
        main_row.setSpacing(16)
        main_row.addWidget(self._build_vault_card(), 1)

        side = QVBoxLayout()
        side.setSpacing(14)
        side.addWidget(self._build_actions_card())
        self.details_card = self._build_details_card()
        side.addWidget(self.details_card, 1)
        side_holder = QWidget()
        side_holder.setLayout(side)
        side_holder.setFixedWidth(334)
        main_row.addWidget(side_holder)
        body_layout.addLayout(main_row, 1)

        body_layout.addWidget(self._build_automation_card())

        footer = QHBoxLayout()
        footer.setContentsMargins(2, 2, 2, 0)
        vault_link = QPushButton("Vault folder")
        vault_link.setObjectName("Link")
        vault_link.setCursor(Qt.CursorShape.PointingHandCursor)
        vault_link.clicked.connect(lambda: system.reveal_in_file_manager(self.vault.root))
        vault_link.setFont(tracking_font(7, 0.6, bold=False))
        vault_link.setStyleSheet(f"color: {PALETTE['GOLD_DIM']}; padding: 0;")
        self.footer_meta = QLabel("")
        self.footer_meta.setObjectName("Small")
        version = QLabel(f"BONFIRE {paths.VERSION}")
        version.setObjectName("Small")
        version.setFont(tracking_font(6, 1.2, bold=False))
        footer.addWidget(vault_link)
        footer.addWidget(self.footer_meta)
        footer.addStretch(1)
        footer.addWidget(version)
        body_layout.addLayout(footer)

    def _build_save_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedHeight(106)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 13, 16, 13)
        layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_eyebrow("Save file"))
        self.save_state_dot = QLabel("●")
        self.save_state_dot.setStyleSheet(f"color: {PALETTE['GOLD']}; font-size: 10px;")
        top.addWidget(self.save_state_dot)
        top.addStretch(1)
        left.addLayout(top)

        self.file_name = QLabel("Searching…")
        self.file_name.setObjectName("FileName")
        left.addWidget(self.file_name)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.save_meta = QLabel("")
        self.save_meta.setObjectName("Muted")
        self.source_label = QLabel("")
        self.source_label.setObjectName("Small")
        meta_row.addWidget(self.save_meta)
        meta_row.addWidget(self.source_label)
        meta_row.addStretch(1)
        left.addLayout(meta_row)

        self.save_path = ElidedLabel("")
        self.save_path.setObjectName("Mono")
        self.save_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        left.addWidget(self.save_path)

        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.detect_btn = QPushButton("Auto-detect")
        self.detect_btn.setObjectName("Ghost")
        self.detect_btn.setToolTip("Search Steam, Proton and Wine folders (F5)")
        self.detect_btn.clicked.connect(self._auto_detect)
        self.change_btn = QPushButton("Change…")
        self.change_btn.setObjectName("Ghost")
        self.change_btn.setToolTip("Choose a save file manually (Ctrl+O)")
        self.change_btn.clicked.connect(self._choose_file)
        self.reveal_btn = QPushButton("Open folder")
        self.reveal_btn.setObjectName("Ghost")
        self.reveal_btn.clicked.connect(self._reveal_save)
        buttons.addWidget(self.detect_btn)
        buttons.addWidget(self.change_btn)
        buttons.addWidget(self.reveal_btn)
        right.addLayout(buttons)

        self.detect_note = ElidedLabel("")
        self.detect_note.setObjectName("Small")
        self.detect_note.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.detect_note.setFixedWidth(300)
        right.addWidget(self.detect_note, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(right)

        return card

    def _build_vault_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 10)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(_eyebrow("Snapshots"))
        head.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("Small")
        head.addWidget(self.count_label)
        layout.addLayout(head)

        self.table = QTreeWidget()
        self.table.setObjectName("VaultTable")
        self.table.setColumnCount(4)
        self.table.setHeaderLabels(["WHEN", "TYPE", "SIZE", "NOTE"])
        self.table.setRootIsDecorated(False)
        self.table.setIndentation(0)
        self.table.setUniformRowHeights(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.itemDoubleClicked.connect(lambda *_: self._request_restore())
        self.table.customContextMenuRequested.connect(self._table_menu)

        header = self.table.header()
        header.setFont(tracking_font(6, 1.4))
        header.setFixedHeight(30)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(0, 158)
        header.resizeSection(1, 118)
        header.resizeSection(2, 74)
        header.setHighlightSections(False)
        self.table.setItemDelegateForColumn(1, KindBadgeDelegate(self.table))

        self.empty = EmptyVault()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack, 1)
        return card

    def _build_actions_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(_eyebrow("Actions"))

        self.boss_btn = QPushButton("⚔   BOSS BACKUP")
        self.boss_btn.setObjectName("Boss")
        self.boss_btn.setMinimumHeight(56)
        self.boss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boss_btn.setToolTip("Take a pinned snapshot before a fight (Ctrl+B)")
        self.boss_btn.clicked.connect(lambda: self._manual_backup(KIND_BOSS))
        layout.addWidget(self.boss_btn)

        hint = QLabel("Pinned · never removed by automatic cleanup")
        hint.setObjectName("Small")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)
        layout.addSpacing(2)

        self.backup_btn = QPushButton("Backup now")
        self.backup_btn.setMinimumHeight(36)
        self.backup_btn.setToolTip("Take a manual snapshot (Ctrl+N)")
        self.backup_btn.clicked.connect(lambda: self._manual_backup(KIND_MANUAL))
        layout.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore selected…")
        self.restore_btn.setObjectName("Restore")
        self.restore_btn.setMinimumHeight(38)
        self.restore_btn.clicked.connect(self._request_restore)
        layout.addWidget(self.restore_btn)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setObjectName("Ghost")
        self.verify_btn.clicked.connect(self._verify_selected)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.clicked.connect(self._delete_selected)
        row.addWidget(self.verify_btn)
        row.addWidget(self.delete_btn)
        layout.addLayout(row)
        return card

    def _build_details_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(_eyebrow("Selected snapshot"))

        self.detail_title = QLabel("Nothing selected")
        self.detail_title.setObjectName("DetailTitle")
        self.detail_title.setWordWrap(True)
        layout.addWidget(self.detail_title)

        self.detail_meta = QLabel("Select a snapshot to inspect it.")
        self.detail_meta.setObjectName("Muted")
        self.detail_meta.setWordWrap(True)
        layout.addWidget(self.detail_meta)

        self.detail_note = QLabel("")
        self.detail_note.setObjectName("Value")
        self.detail_note.setWordWrap(True)
        layout.addWidget(self.detail_note)

        layout.addStretch(1)
        layout.addWidget(_hline())
        self.detail_hash = QLabel("")
        self.detail_hash.setObjectName("Mono")
        self.detail_hash.setWordWrap(True)
        self.detail_hash.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail_hash)
        return card

    def _build_automation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 11, 18, 11)
        layout.setSpacing(20)

        auto = QVBoxLayout()
        auto.setSpacing(3)
        auto.addWidget(_eyebrow("Automatic backups"))
        row = QHBoxLayout()
        row.setSpacing(7)
        self.auto_switch = Switch()
        self.auto_switch.setToolTip("Enable periodic snapshots while Bonfire is open")
        self.auto_switch.toggled.connect(self._on_auto_toggled)
        row.addWidget(self.auto_switch)
        every = QLabel("Every")
        every.setObjectName("Muted")
        row.addWidget(every)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 24 * 60)
        self.interval_spin.setSuffix(" min")
        self.interval_spin.setFixedWidth(86)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        row.addWidget(self.interval_spin)
        self.changed_check = QCheckBox("Only when the save has changed")
        self.changed_check.toggled.connect(self._on_only_changed_toggled)
        row.addWidget(self.changed_check)
        row.addStretch(1)
        auto.addLayout(row)
        layout.addLayout(auto, 1)

        layout.addWidget(_vline())

        retention = QVBoxLayout()
        retention.setSpacing(3)
        retention.addWidget(_eyebrow("Retention"))
        keep_row = QHBoxLayout()
        keep_row.setSpacing(7)
        keep = QLabel("Keep up to")
        keep.setObjectName("Muted")
        keep_row.addWidget(keep)
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 500)
        self.retention_spin.setFixedWidth(70)
        self.retention_spin.setToolTip("Unpinned snapshots kept; pinned snapshots are never deleted")
        self.retention_spin.valueChanged.connect(self._on_retention_changed)
        keep_row.addWidget(self.retention_spin)
        unpinned_label = QLabel("unpinned")
        unpinned_label.setObjectName("Muted")
        keep_row.addWidget(unpinned_label)
        keep_row.addStretch(1)
        retention.addLayout(keep_row)
        layout.addLayout(retention)

        layout.addWidget(_vline())

        nxt = QVBoxLayout()
        nxt.setSpacing(0)
        label_row = QHBoxLayout()
        label_row.setSpacing(8)
        label_row.addWidget(_eyebrow("Next snapshot"))
        self.auto_note = QLabel("")
        self.auto_note.setObjectName("Small")
        label_row.addWidget(self.auto_note)
        label_row.addStretch(1)
        nxt.addLayout(label_row)
        self.countdown = QLabel("—")
        self.countdown.setObjectName("Countdown")
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignLeft)
        nxt.addWidget(self.countdown)
        self.countdown_holder = QWidget()
        self.countdown_holder.setLayout(nxt)
        self.countdown_holder.setFixedWidth(232)
        layout.addWidget(self.countdown_holder)
        return card

    # ------------------------------------------------------------- settings
    def _apply_settings_to_ui(self) -> None:
        self._loading = True
        self.auto_switch.setChecked(self.settings.auto_enabled)
        self.interval_spin.setValue(self.settings.interval_min)
        self.retention_spin.setValue(self.settings.max_backups)
        self.changed_check.setChecked(self.settings.only_when_changed)
        self._loading = False

    def _persist(self) -> None:
        try:
            config.save(self.settings)
        except OSError as exc:
            log.exception("Could not save settings")
            self._toast(f"Could not save settings: {exc}", "warn")

    def _on_auto_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self.settings.auto_enabled = checked
        self._persist()
        self._reset_schedule()
        if checked:
            self._toast("Automatic backups enabled.", "ok")
        else:
            self._toast("Automatic backups paused.", "muted")

    def _on_interval_changed(self, value: int) -> None:
        if self._loading:
            return
        self.settings.interval_min = value
        self._persist()
        self._reset_schedule()

    def _on_retention_changed(self, value: int) -> None:
        if self._loading:
            return
        self.settings.max_backups = value
        self._persist()
        removed = self.vault.prune(value)
        self._refresh_table(select_id=self._selected_id)
        if removed:
            self._toast(f"Retention applied — {len(removed)} old snapshot(s) removed.", "muted")

    def _on_only_changed_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self.settings.only_when_changed = checked
        self._persist()

    # ---------------------------------------------------------------- startup
    def _load_initial_save(self) -> None:
        override = self.settings.save_file
        if override:
            candidate = Path(override).expanduser()
            if candidate.is_file():
                self.save_file = candidate
                self._source = "Manually selected"
                return
        self._run_detection(initial=True)

    def _run_detection(self, initial: bool = False) -> detect.Detection:
        result = detect.detect()
        self.detection = result
        if result.found and result.save_file is not None:
            self.save_file = result.save_file
            self._source = result.source
        else:
            self.save_file = None
            self._source = ""
            if not initial:
                self._toast("No save found. Is the game installed or Proton prefix intact?", "warn")
        return result

    def _auto_detect(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self._run_detection()
        finally:
            QApplication.restoreOverrideCursor()

        if result.found:
            # Auto-detect intentionally clears a manual override.
            self.settings.save_file = None
            self._persist()
            self._refresh_save_card()
            self._refresh_table(select_id=self._selected_id)
            self._reset_schedule()
            self._toast("Save located automatically.", "ok")
        else:
            self._refresh_save_card()
            self._toast("No save file found. Choose one manually if needed.", "warn")

    def _choose_file(self) -> None:
        start = str(self.save_file.parent) if self.save_file else str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select DRAKS0005.sl2",
            start,
            "Dark Souls save (DRAKS0005.sl2);;All files (*)",
        )
        if not chosen:
            return
        path = Path(chosen)
        valid, reason = system.save_looks_valid(path)
        if not valid and not _confirm(
            self,
            "Unrecognised save file",
            f"{reason}\n\nUse it anyway? Bonfire will still snapshot and verify it byte-for-byte, "
            "but restoring an unrelated file could confuse the game.",
            "Use anyway",
        ):
            return
        self.save_file = path
        self._source = "Manually selected"
        self.settings.save_file = str(path)
        self._persist()
        self._refresh_save_card()
        self._refresh_table(select_id=self._selected_id)
        self._reset_schedule()
        self._toast("Save file linked.", "ok")

    def _reveal_save(self) -> None:
        if self.save_file:
            system.reveal_in_file_manager(self.save_file)
        else:
            system.reveal_in_file_manager(self.vault.root)

    def _wire_shortcuts(self) -> None:
        for keys, slot in (
            ("Ctrl+B", lambda: self._manual_backup(KIND_BOSS)),
            ("Ctrl+N", lambda: self._manual_backup(KIND_MANUAL)),
            ("Ctrl+O", self._choose_file),
            ("F5", self._auto_detect),
            ("Delete", self._delete_selected),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)

    # -------------------------------------------------------------- status
    def _save_ready(self) -> bool:
        return bool(self.save_file and self.save_file.is_file())

    def _refresh_save_card(self) -> None:
        self.empty.set_linked(self._save_ready())
        if not self._save_ready():
            self.file_name.setText("No save found")
            self.detect_note.setText("Searched Steam · Proton · Wine")
            if self.settings.save_file:
                self.save_meta.setText("The linked file is missing.")
                self.save_path.setText(_display_path(Path(self.settings.save_file)))
            else:
                self.save_meta.setText("Launch the game once and save, then rescan.")
                self.save_path.setText("DRAKS0005.sl2 was not found in the usual places.")
            self.save_state_dot.setStyleSheet(f"color: {PALETTE['RED']}; font-size: 10px;")
            self.save_chip.set_state("NO SAVE", "warn")
            self.source_label.setText("")
            self._update_buttons()
            return

        assert self.save_file is not None
        try:
            stat = self.save_file.stat()
        except OSError:
            self.save_file = None
            self._refresh_save_card()
            return

        valid, reason = system.save_looks_valid(self.save_file)
        self.file_name.setText(self.save_file.name)
        self.save_meta.setText(f"{system.human_size(stat.st_size)}   ·   saved {_age_text(stat.st_mtime)}")
        self.save_path.setText(_display_path(self.save_file))
        self.source_label.setText(f"via {self._source}" if self._source else "")
        self.save_state_dot.setStyleSheet(f"color: {PALETTE['GOLD'] if valid else PALETTE['EMBER']}; font-size: 10px;")
        self.save_chip.set_state("SAVE LINKED" if valid else "CHECK FILE", "ok" if valid else "warn")
        if not valid:
            note = reason
        elif self.save_file.parent.name.isdigit() and len(self.save_file.parent.name) >= 6:
            note = f"Steam ID {self.save_file.parent.name}"
        else:
            note = "BND4 save container"
        self.detect_note.setText(note)
        self.detect_note.setToolTip(reason or note)
        self._update_buttons()

    def _poll_game(self, initial: bool = False) -> None:
        running = system.game_running()
        changed = running != self._game_running
        self._game_running = running
        self.game_chip.set_state("GAME RUNNING" if running else "GAME CLOSED", "warn" if running else "muted")
        if changed and not initial:
            if running:
                self._toast("Dark Souls is running — restoring is locked until you quit.", "warn")
            else:
                self._toast("Game closed. Restore is available.", "ok")
        self._update_buttons()

    def _periodic_refresh(self) -> None:
        self._refresh_save_card()
        if not self._save_ready() and time.monotonic() - self._last_missing_scan > 25:
            self._last_missing_scan = time.monotonic()
            result = detect.detect()
            if result.found:
                self.save_file = result.save_file
                self._source = result.source
                self.detection = result
                self._refresh_save_card()
                self._reset_schedule()
                self._toast("Save file found.", "ok")
                return
        self._update_countdown()

    # ------------------------------------------------------------ schedule
    def _tick(self) -> None:
        self._update_countdown()
        if self._next_due is None:
            return
        if time.monotonic() >= self._next_due:
            self._next_due = time.monotonic() + self.settings.interval_min * 60
            self._auto_backup()

    def _reset_schedule(self) -> None:
        if self.settings.auto_enabled and self._save_ready():
            self._next_due = time.monotonic() + self.settings.interval_min * 60
        else:
            self._next_due = None
        self._update_countdown()

    def _update_countdown(self) -> None:
        if not self.settings.auto_enabled:
            self.countdown.setText("PAUSED")
            self.auto_note.setText("off")
            return
        if not self._save_ready() or self._next_due is None:
            self.countdown.setText("—")
            self.auto_note.setText("waiting for a save" if not self._save_ready() else "")
            return
        remaining = max(0, int(self._next_due - time.monotonic() + 0.5))
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            self.countdown.setText(f"{hours}:{minutes:02d}:{seconds:02d}")
        else:
            self.countdown.setText(f"{minutes:02d}:{seconds:02d}")
        if self.auto_note.text() in ("off", "waiting for a save"):
            self.auto_note.setText("")

    def _auto_backup(self) -> None:
        if not self._save_ready():
            return
        assert self.save_file is not None
        try:
            if self.settings.only_when_changed:
                latest = self.vault.latest()
                if latest and latest.sha256 and sha256_file(self.save_file) == latest.sha256:
                    self.auto_note.setText("skipped · unchanged")
                    return
            backup = self.vault.create(self.save_file, kind=KIND_AUTO)
            removed = self.vault.prune(self.settings.max_backups)
        except Exception as exc:
            log.exception("Automatic backup failed")
            self._toast(f"Automatic backup failed: {exc}", "warn")
            return
        log.info("Automatic snapshot %s", backup.id)
        self._after_backup(backup, removed, "Automatic snapshot saved")
        self._refresh_save_card()

    def _manual_backup(self, kind: str) -> None:
        if not self._save_ready():
            _notice(
                self,
                "No save file",
                "Bonfire has not located DRAKS0005.sl2 yet. Rescan, or choose the file manually.",
                tone="warn",
            )
            return
        assert self.save_file is not None
        try:
            backup = self.vault.create(self.save_file, kind=kind, note="")
            removed = self.vault.prune(self.settings.max_backups)
        except Exception as exc:
            log.exception("Backup failed")
            _notice(
                self,
                "Backup failed",
                f"The snapshot could not be written.\n\n{exc}",
                tone="error",
                ok_text="Close",
            )
            return
        log.info("Manual snapshot %s (%s)", backup.id, kind)
        message = "Boss backup sealed — pinned." if kind == KIND_BOSS else "Snapshot saved."
        self._after_backup(backup, removed, message)

    def _after_backup(self, backup: Backup, removed: list[Backup], message: str) -> None:
        self._reset_schedule()
        self._refresh_table(select_id=backup.id)
        self._refresh_save_card()
        if backup.kind == KIND_AUTO:
            self.auto_note.setText(f"saved {backup.created_at.astimezone():%H:%M}")
        if removed:
            message += f" {len(removed)} old snapshot(s) rotated out."
        self._toast(message, "ok")

    # --------------------------------------------------------------- table
    def _refresh_table(self, select_id: str | None = None) -> None:
        backups = self.vault.list()
        self._refresh_table_rows(backups)
        self.count_label.setText(
            f"{len(backups)} snapshot{'s' if len(backups) != 1 else ''} · {system.human_size(self.vault.total_size())}"
        )
        self.footer_meta.setText(f"  ·  {_display_path(self.vault.root)}")

        target_id = select_id or self._selected_id
        if backups:
            self.stack.setCurrentIndex(0)
            row_to_select = 0
            for index, backup in enumerate(backups):
                if backup.id == target_id:
                    row_to_select = index
                    break
            self.table.setCurrentItem(self.table.topLevelItem(row_to_select))
            self.table.scrollToItem(self.table.topLevelItem(row_to_select))
        else:
            self._selected_id = None
            self.stack.setCurrentIndex(1)
            self._update_details()
        self._update_buttons()

    def _refresh_table_rows(self, backups: list[Backup]) -> None:
        self.table.blockSignals(True)
        self.table.clear()
        for backup in backups:
            item = QTreeWidgetItem()
            item.setText(0, _when_text(backup.created_at))
            item.setToolTip(0, _stamp(backup.created_at, weekday=True, seconds=True).replace(" · ", " at "))
            item.setText(1, backup.kind_label)
            item.setData(1, Qt.ItemDataRole.UserRole, {"kind": backup.kind, "pinned": backup.pinned})
            item.setText(2, system.human_size(backup.size))
            item.setToolTip(2, f"{backup.size:,} bytes")
            item.setText(3, backup.note if backup.note else "—")
            item.setToolTip(3, backup.note or "No note")
            item.setData(0, Qt.ItemDataRole.UserRole, backup.id)
            for column in range(4):
                item.setTextAlignment(column, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.addTopLevelItem(item)
        self.table.blockSignals(False)

    def _selected_backup(self) -> Backup | None:
        if not self._selected_id:
            return None
        return self.vault.get(self._selected_id)

    def _on_selection(self) -> None:
        items = self.table.selectedItems()
        self._selected_id = items[0].data(0, Qt.ItemDataRole.UserRole) if items else None
        self._update_details()
        self._update_buttons()

    def _update_details(self) -> None:
        backup = self._selected_backup()
        if backup is None:
            self.detail_title.setText("Nothing selected")
            self.detail_meta.setText("Select a snapshot to inspect it.")
            self.detail_note.setText("")
            self.detail_hash.setText("")
            return
        self.detail_title.setText(_stamp(backup.created_at))
        flags = [f"{backup.kind_label} snapshot", system.human_size(backup.size)]
        if backup.pinned:
            flags.append("pinned")
        self.detail_meta.setText("  ·  ".join(flags))
        self.detail_note.setText(f"“{backup.note}”" if backup.note else "No note attached.")
        self.detail_hash.setText(
            f"SHA-256\n{backup.sha256[:32]}\n{backup.sha256[32:]}"
        )
        self.detail_hash.setToolTip(backup.sha256)

    def _update_buttons(self) -> None:
        ready = self._save_ready()
        selected = self._selected_id is not None
        self.boss_btn.setEnabled(ready)
        self.backup_btn.setEnabled(ready)
        self.restore_btn.setEnabled(selected and not self._game_running)
        if self._game_running:
            self.restore_btn.setToolTip("Close Dark Souls before restoring.")
        else:
            self.restore_btn.setToolTip("Replace the current save with the selected snapshot")
        self.verify_btn.setEnabled(selected)
        self.delete_btn.setEnabled(selected)
        self.reveal_btn.setEnabled(ready)

    def _table_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        self.table.setCurrentItem(item)
        menu = QMenu(self)
        restore = QAction("Restore this snapshot…", menu)
        restore.triggered.connect(self._request_restore)
        note = QAction("Edit note…", menu)
        note.triggered.connect(self._edit_note)
        verify = QAction("Verify integrity", menu)
        verify.triggered.connect(self._verify_selected)
        delete = QAction("Delete snapshot", menu)
        delete.triggered.connect(self._delete_selected)
        menu.addAction(restore)
        menu.addAction(note)
        menu.addAction(verify)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _edit_note(self) -> None:
        backup = self._selected_backup()
        if backup is None:
            return
        text, ok = QInputDialog.getText(
            self, "Snapshot note", "What is worth remembering about this moment?",
            text=backup.note,
        )
        if not ok:
            return
        try:
            self.vault.update_note(backup, text)
        except Exception as exc:  # noqa: BLE001 - GUI boundary
            _notice(self, "Could not save note", str(exc), tone="error", ok_text="Close")
            return
        self._refresh_table(select_id=backup.id)
        self._toast("Note updated.", "ok")

    # ------------------------------------------------------------- actions
    def _request_restore(self) -> None:
        backup = self._selected_backup()
        if backup is None:
            return
        if system.game_running():
            self._poll_game()
            _notice(
                self,
                "Dark Souls is running",
                "Close Dark Souls before restoring. The game holds the save in memory and "
                "rewrites it on exit, which would undo the restore.",
                tone="warn",
            )
            return
        target = self.save_file or Path(backup.source_path)
        if not target.parent.is_dir():
            _notice(
                self,
                "Save folder unavailable",
                f"The folder for this save no longer exists.\n\n{_display_path(target.parent)}\n\n"
                "Launch the game once to recreate it, then restore again.",
                tone="error",
                ok_text="Close",
            )
            return

        dialog = RestoreDialog(backup, target, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            safety = restore_backup(
                backup, target, vault=self.vault, make_safety=dialog.make_safety
            )
        except Exception as exc:
            log.exception("Restore failed")
            _notice(self, "Restore failed", str(exc), tone="error", ok_text="Close")
            return

        if self.save_file is None:
            self.save_file = target
            self.settings.save_file = str(target)
            self._persist()
        log.info("Restored %s to %s (safety=%s)", backup.id, target, safety.id if safety else "none")
        self._refresh_save_card()
        self._refresh_table(select_id=backup.id)
        self._reset_schedule()
        message = "Save restored. Launch the game once Steam Cloud is settled."
        if safety:
            message = f"Save restored · safety copy {safety.id} kept."
        self._toast(message, "ok")

    def _verify_selected(self) -> None:
        backup = self._selected_backup()
        if backup is None:
            return
        if self.vault.verify(backup):
            _notice(
                self,
                "Snapshot intact",
                f"{backup.id}\n\nSHA-256 matches the bytes captured at backup time.",
                tone="info",
                ok_text="Close",
            )
        else:
            _notice(
                self,
                "Snapshot damaged",
                f"{backup.id}\n\nThe file on disk no longer matches its checksum. "
                "Do not restore it; delete it and use an older snapshot.",
                tone="error",
                ok_text="Close",
            )

    def _delete_selected(self) -> None:
        backup = self._selected_backup()
        if backup is None:
            return
        extra = "\n\nThis snapshot is pinned." if backup.pinned else ""
        if not _confirm(
            self,
            "Delete this snapshot?",
            f"{backup.id}\n\n{_stamp(backup.created_at)} · "
            f"{system.human_size(backup.size)}{extra}\n\nThis cannot be undone.",
            "Delete",
            destructive=True,
        ):
            return
        try:
            self.vault.delete(backup)
        except OSError as exc:
            _notice(self, "Delete failed", str(exc), tone="error", ok_text="Close")
            return
        self._selected_id = None
        self._refresh_table()
        self._toast("Snapshot deleted.", "muted")

    def _toast(self, message: str, tone: str = "gold") -> None:
        if hasattr(self, "toast"):
            self.toast.show_message(message, tone)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "details_card"):
            # The side column cannot fit both cards on short screens; keep the
            # actions usable rather than letting the layout squeeze them.
            self.details_card.setVisible(event.size().height() >= 860)
        if hasattr(self, "toast") and self.toast.isVisible():
            parent = self.toast.parentWidget()
            if parent:
                self.toast.move(
                    max(12, (parent.width() - self.toast.width()) // 2),
                    parent.height() - self.toast.height() - 120,
                )
