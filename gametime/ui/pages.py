"""主界面的四个页面：概览、游戏库、统计、设置。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..models import GameSummary, Overview
from ..paths import AppPaths
from ..services.library import GameService
from ..services.settings import AutostartManager, SettingsStore
from ..services.stats import StatsService
from ..services.tracking import TrackingEngine
from .dialogs_confirm import show_message
from .formatting import (
    WEEKDAYS,
    format_big_duration,
    format_date_heading,
    format_duration,
    greeting,
)
from .icons import icon, pixmap
from .theme import COLORS
from .widgets import (
    BarChart,
    CardFrame,
    EmptyState,
    FlowLayout,
    GameCard,
    GameIcon,
    RankBar,
    Separator,
    SmallButton,
    SoftComboBox,
    StatCard,
    ToggleRow,
    pill,
)


def _clear_layout(layout) -> None:  # noqa: ANN001
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


class ScrollPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("Page")
        self.content = QVBoxLayout(content)
        self.content.setContentsMargins(30, 26, 30, 28)
        self.content.setSpacing(18)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.scroll = scroll


def _page_header(title: str, subtitle: str, actions: QWidget | None = None) -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(14)
    text = QVBoxLayout()
    text.setSpacing(3)
    heading = QLabel(title)
    heading.setProperty("role", "h1")
    sub = QLabel(subtitle)
    sub.setProperty("role", "muted")
    text.addWidget(heading)
    text.addWidget(sub)
    row.addLayout(text)
    row.addStretch(1)
    if actions is not None:
        row.addWidget(actions)
    return holder


def _primary_button(text: str, icon_name: str = "plus") -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "primary")
    button.setIcon(icon(icon_name, "#FFFFFF", 16))
    button.setIconSize(QSize(16, 16))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(37)
    return button


# ---------------------------------------------------------------------------
class DashboardPage(ScrollPage):
    addRequested = Signal()
    openGame = Signal(int)
    quickAction = Signal(int)
    showLibrary = Signal()

    def __init__(self, library: GameService, stats: StatsService, tracker: TrackingEngine, parent=None) -> None:
        super().__init__()
        self.setParent(parent)
        self.library = library
        self.stats = stats
        self.tracker = tracker
        self._cards: dict[int, GameCard] = {}
        self._games: list[GameSummary] = []
        self._live_game_id: int | None = None
        self._overview = Overview()
        self._build()

    def _build(self) -> None:
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setProperty("variant", "ghost")
        self.refresh_button.setIcon(icon("refresh", COLORS["muted"], 15))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh)

        add = _primary_button("添加游戏")
        add.clicked.connect(self.addRequested)
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addWidget(add)

        self.header_holder = QWidget()
        header_layout = QHBoxLayout(self.header_holder)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.greeting_label = QLabel("晚上好，玩家")
        self.greeting_label.setProperty("role", "h1")
        self.date_label = QLabel(format_date_heading())
        self.date_label.setProperty("role", "muted")
        text.addWidget(self.greeting_label)
        text.addWidget(self.date_label)
        header_layout.addLayout(text)
        header_layout.addStretch(1)
        header_layout.addWidget(actions)
        self.content.addWidget(self.header_holder)

        # 今日主卡 + 两个辅助卡
        summary_row = QHBoxLayout()
        summary_row.setSpacing(14)
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero.setMinimumHeight(132)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 17, 22, 17)
        hero_layout.setSpacing(14)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(5)
        hero_top = QHBoxLayout()
        hero_top.setSpacing(7)
        badge = QLabel()
        badge.setPixmap(pixmap("spark", "#C4B5FF", 15))
        hero_top.addWidget(badge)
        today_title = QLabel("今日游玩")
        today_title.setStyleSheet("color: #C8BFFF; font-size: 12px; font-weight: 600;")
        hero_top.addWidget(today_title)
        hero_top.addStretch(1)
        self.today_pill = pill("实时记录", "purple")
        hero_top.addWidget(self.today_pill)
        hero_text.addLayout(hero_top)
        self.today_value = QLabel("0 分钟")
        self.today_value.setStyleSheet(
            f"font-family: {QFont('Segoe UI Variable Display').family()}; "
            "font-size: 33px; font-weight: 700; color: #F4F1FF; background: transparent;"
        )
        hero_text.addWidget(self.today_value)
        self.today_meta = QLabel("还没有开始今天的游戏")
        self.today_meta.setStyleSheet("color: #9C93BE; font-size: 12px; background: transparent;")
        hero_text.addWidget(self.today_meta)
        hero_layout.addLayout(hero_text, 1)
        self.hero_art = QLabel()
        self.hero_art.setPixmap(pixmap("gamepad", "#6F5BD6", 70))
        self.hero_art.setFixedSize(84, 84)
        self.hero_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_art.setStyleSheet(
            "background: rgba(124, 92, 255, 34); border: 1px solid rgba(150, 125, 255, 38); "
            "border-radius: 25px;"
        )
        hero_layout.addWidget(self.hero_art, 0, Qt.AlignmentFlag.AlignVCenter)
        summary_row.addWidget(hero, 3)

        self.week_card = StatCard(
            "近 7 天", "0 分钟", "保持节奏，慢慢积累", icon_name="calendar", accent=COLORS["green"]
        )
        self.library_card = StatCard(
            "游戏库", "0 款", "手动添加，只记录你的游戏", icon_name="library", accent=COLORS["blue"]
        )
        summary_row.addWidget(self.week_card, 2)
        summary_row.addWidget(self.library_card, 2)
        self.content.addLayout(summary_row)

        # 正在游玩
        self.live_card = QFrame()
        self.live_card.setObjectName("LiveCard")
        live_layout = QHBoxLayout(self.live_card)
        live_layout.setContentsMargins(16, 12, 16, 12)
        live_layout.setSpacing(13)
        self.live_icon = GameIcon(44)
        live_layout.addWidget(self.live_icon)
        live_text = QVBoxLayout()
        live_text.setSpacing(2)
        live_top = QHBoxLayout()
        live_top.setSpacing(7)
        self.live_dot = QLabel()
        self.live_dot.setFixedSize(7, 7)
        self.live_dot.setStyleSheet(f"background: {COLORS['green']}; border-radius: 3px;")
        live_top.addWidget(self.live_dot)
        self.live_name = QLabel("")
        self.live_name.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
        live_top.addWidget(self.live_name)
        self.live_source = QLabel("")
        self.live_source.setStyleSheet("color: #8FAEA4; font-size: 11px; background: transparent;")
        live_top.addWidget(self.live_source)
        live_top.addStretch(1)
        live_text.addLayout(live_top)
        self.live_meta = QLabel("")
        self.live_meta.setStyleSheet("color: #79958D; font-size: 11px; background: transparent;")
        live_text.addWidget(self.live_meta)
        live_layout.addLayout(live_text, 1)
        self.live_elapsed = QLabel("00:00:00")
        self.live_elapsed.setStyleSheet(
            "font-family: 'Segoe UI Variable Display'; font-size: 20px; font-weight: 700; "
            f"color: {COLORS['green']}; background: transparent;"
        )
        live_layout.addWidget(self.live_elapsed)
        self.live_open = QPushButton("查看")
        self.live_open.setStyleSheet(
            "QPushButton { background: #1D3D34; border: 1px solid #2E5E50; color: #8DE6C8; "
            "border-radius: 9px; padding: 7px 13px; font-size: 12px; }"
            "QPushButton:hover { background: #265043; }"
        )
        self.live_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.live_open.clicked.connect(self._open_live)
        live_layout.addWidget(self.live_open)
        self.live_card.hide()
        self.content.addWidget(self.live_card)

        # 最近游玩
        recent_header = QHBoxLayout()
        recent_title = QLabel("最近游玩")
        recent_title.setProperty("role", "h2")
        recent_header.addWidget(recent_title)
        recent_header.addStretch(1)
        all_button = QPushButton("全部游戏")
        all_button.setProperty("variant", "ghost")
        all_button.setIcon(icon("chevron-right", COLORS["muted"], 14))
        all_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        all_button.clicked.connect(self.showLibrary)
        recent_header.addWidget(all_button)
        self.content.addLayout(recent_header)

        self.recent_holder = QWidget()
        self.recent_flow = FlowLayout(self.recent_holder, spacing=14)
        self.recent_flow.setContentsMargins(0, 0, 0, 0)
        self.content.addWidget(self.recent_holder)

        self.empty = EmptyState(
            "把第一款桌面游戏收进来",
            "点击“添加游戏”，选择游戏的 exe。游时只统计你手动添加的游戏，不扫描、不推测。",
            "添加游戏",
            icon_name="gamepad",
        )
        self.empty.button.clicked.connect(self.addRequested)
        self.content.addWidget(self.empty)

        # 图表
        chart_card = CardFrame()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(19, 16, 19, 12)
        chart_layout.setSpacing(3)
        chart_header = QHBoxLayout()
        chart_title = QLabel("近 7 天游玩")
        chart_title.setProperty("role", "h3")
        chart_header.addWidget(chart_title)
        chart_header.addStretch(1)
        self.chart_total = QLabel("0 分钟")
        self.chart_total.setProperty("role", "muted")
        chart_header.addWidget(self.chart_total)
        chart_layout.addLayout(chart_header)
        self.chart = BarChart()
        self.chart.setMinimumHeight(186)
        chart_layout.addWidget(self.chart)
        self.chart_card = chart_card
        self.content.addWidget(chart_card)
        self.content.addStretch(1)

    def refresh(self) -> None:
        self.greeting_label.setText(f"{greeting()}，玩家")
        self.date_label.setText(format_date_heading())
        self._overview = self.stats.overview()
        overview = self._overview
        self.today_value.setText(format_big_duration(overview.today_seconds))
        self.today_meta.setText(
            f"共 {overview.sessions_today} 局 · 自动计时已开启"
            if overview.sessions_today
            else "还没有开始今天的游戏"
        )
        self.week_card.set_value(
            format_duration(overview.last7_seconds, zero="0 分钟"), "近 7 天累计游玩"
        )
        self.library_card.set_value(
            f"{overview.game_count} 款", f"累计 {format_duration(overview.total_seconds, zero='0 分钟')}"
        )
        self.chart_total.setText(format_duration(overview.last7_seconds, zero="0 分钟"))
        self._fill_chart(overview)
        self._games = self.library.list_games(sort="recent")
        self._rebuild_recent()
        self.changed_visibility = bool(self._games)
        self._update_live()

    def _fill_chart(self, overview: Overview) -> None:
        values = []
        for day_string, seconds in overview.daily:
            day = date.fromisoformat(day_string)
            values.append((WEEKDAYS[day.weekday()], seconds))
        self.chart.set_data(values)

    def _rebuild_recent(self) -> None:
        for card in self._cards.values():
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        _clear_layout(self.recent_flow)
        show = self._games[:4]
        self.empty.setVisible(not self._games)
        self.recent_holder.setVisible(bool(self._games))
        self.chart_card.setVisible(bool(self._games))
        for summary in show:
            card = GameCard(summary, self.library.icons, width=330)
            card.clicked.connect(self.openGame)
            card.action_requested.connect(self.quickAction)
            self.recent_flow.addWidget(card)
            self._cards[summary.game.id] = card
        self._update_live()

    def _update_live(self) -> None:
        active = self.tracker.active_runs
        for game_id, card in self._cards.items():
            source = self.tracker.active_source(game_id)
            card.set_live(source is not None, source, self.tracker.live_elapsed(game_id))
        if not active:
            self.live_card.hide()
            self._live_game_id = None
            return
        game_id = next(iter(active))
        try:
            game = self.library.get_game(game_id)
        except Exception:
            self.live_card.hide()
            return
        self._live_game_id = game_id
        self.live_card.show()
        self.live_icon.set_game(game, self.library.icon_path(game))
        self.live_name.setText(game.name)
        source = self.tracker.active_source(game_id)
        self.live_source.setText("自动计时" if source == "auto" else "手动计时")
        extra = len(active) - 1
        self.live_meta.setText(f"另有 {extra} 款游戏正在计时" if extra else "进程结束后自动保存时长")
        self.live_elapsed.setText(_clock(self.tracker.live_elapsed(game_id)))

    def refresh_live(self) -> None:
        if not self._cards:
            return
        for game_id, card in self._cards.items():
            source = self.tracker.active_source(game_id)
            card.set_live(source is not None, source, self.tracker.live_elapsed(game_id))
        if self._live_game_id is not None:
            self.live_elapsed.setText(_clock(self.tracker.live_elapsed(self._live_game_id)))

    def _open_live(self) -> None:
        if self._live_game_id is not None:
            self.openGame.emit(self._live_game_id)


def _clock(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
class LibraryPage(ScrollPage):
    addRequested = Signal()
    openGame = Signal(int)
    quickAction = Signal(int)

    def __init__(self, library: GameService, tracker: TrackingEngine) -> None:
        super().__init__()
        self.library = library
        self.tracker = tracker
        self._cards: dict[int, GameCard] = {}
        self._games: list[GameSummary] = []
        self._build()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self.refresh)

    def _build(self) -> None:
        add = _primary_button("添加游戏")
        add.clicked.connect(self.addRequested)
        self.content.addWidget(
            _page_header("游戏库", "这里只会有你手动添加的游戏，不扫描硬盘，也没有自动识别条目。", add)
        )

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索游戏名称或文件名")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(36)
        self.search.addAction(icon("search", COLORS["muted"], 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        controls.addWidget(self.search, 1)
        self.sort_combo = SoftComboBox()
        self.sort_combo.addItem("最近游玩", "recent")
        self.sort_combo.addItem("游玩时长", "playtime")
        self.sort_combo.addItem("名称", "name")
        self.sort_combo.setMinimumWidth(132)
        self.sort_combo.setMinimumHeight(36)
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        controls.addWidget(self.sort_combo)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "muted")
        controls.addWidget(self.count_label)
        self.content.addLayout(controls)

        self.holder = QWidget()
        self.flow = FlowLayout(self.holder, spacing=14)
        self.flow.setContentsMargins(0, 0, 0, 0)
        self.content.addWidget(self.holder)

        self.empty = EmptyState(
            "游戏库还是空的",
            "添加游戏后，游时会在你启动它时自动计时；卸载后也会保留名称、图标与历史。",
            "添加第一款游戏",
        )
        self.empty.button.clicked.connect(self.addRequested)
        self.content.addWidget(self.empty)

        self.no_result = EmptyState(
            "没有找到匹配的游戏",
            "换一个关键词试试，或者清空搜索条件。",
            None,
            icon_name="search",
        )
        self.no_result.hide()
        self.content.addWidget(self.no_result)
        self.content.addStretch(1)

    def refresh(self) -> None:
        query = self.search.text().strip()
        sort = self.sort_combo.currentData() or "recent"
        self._games = self.library.list_games(query, sort)
        total_games = self.library.db.count_games()
        self.count_label.setText(f"共 {total_games} 款")
        for card in self._cards.values():
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        _clear_layout(self.flow)
        self.holder.setVisible(bool(self._games))
        self.empty.setVisible(total_games == 0)
        self.no_result.setVisible(total_games > 0 and not self._games)
        for summary in self._games:
            card = GameCard(summary, self.library.icons, width=330)
            card.clicked.connect(self.openGame)
            card.action_requested.connect(self.quickAction)
            self.flow.addWidget(card)
            self._cards[summary.game.id] = card
        self.refresh_live()

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def refresh_live(self) -> None:
        for game_id, card in self._cards.items():
            source = self.tracker.active_source(game_id)
            card.set_live(source is not None, source, self.tracker.live_elapsed(game_id))


# ---------------------------------------------------------------------------
class StatsPage(ScrollPage):
    exportRequested = Signal()
    openGame = Signal(int)

    def __init__(self, library: GameService, stats: StatsService) -> None:
        super().__init__()
        self.library = library
        self.stats = stats
        self._build()

    def _build(self) -> None:
        export = SmallButton("导出 CSV", "download", variant="soft")
        export.clicked.connect(self.exportRequested)
        self.content.addWidget(
            _page_header("统计", "所有数字都来自你库中的游戏，按照本地时间自然日统计。", export)
        )
        row = QHBoxLayout()
        row.setSpacing(14)
        self.today_card = StatCard("今日", "0 分钟", "今天的游戏时光", icon_name="clock", accent=COLORS["accent"])
        self.week_card = StatCard("近 7 天", "0 分钟", "最近一周", icon_name="calendar", accent=COLORS["green"])
        self.total_card = StatCard("累计", "0 分钟", "所有已记录时长", icon_name="chart", accent=COLORS["blue"])
        row.addWidget(self.today_card)
        row.addWidget(self.week_card)
        row.addWidget(self.total_card)
        self.content.addLayout(row)

        body = QHBoxLayout()
        body.setSpacing(14)
        chart_card = CardFrame()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(19, 16, 19, 12)
        chart_layout.setSpacing(4)
        header = QHBoxLayout()
        title = QLabel("近 14 天")
        title.setProperty("role", "h3")
        header.addWidget(title)
        header.addStretch(1)
        self.chart_sum = QLabel("0 分钟")
        self.chart_sum.setProperty("role", "muted")
        header.addWidget(self.chart_sum)
        chart_layout.addLayout(header)
        self.chart = BarChart()
        self.chart.setMinimumHeight(220)
        chart_layout.addWidget(self.chart)
        body.addWidget(chart_card, 3)

        rank_card = CardFrame()
        rank_layout = QVBoxLayout(rank_card)
        rank_layout.setContentsMargins(17, 16, 17, 14)
        rank_layout.setSpacing(10)
        rank_title = QLabel("游戏排行")
        rank_title.setProperty("role", "h3")
        rank_layout.addWidget(rank_title)
        self.rank_holder = QVBoxLayout()
        self.rank_holder.setSpacing(2)
        rank_layout.addLayout(self.rank_holder)
        rank_layout.addStretch(1)
        body.addWidget(rank_card, 2)
        self.content.addLayout(body)
        self.content.addStretch(1)
        self.empty_hint = QLabel("开始游玩后，这里会出现你的时长趋势和游戏排行。")
        self.empty_hint.setProperty("role", "muted")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content.addWidget(self.empty_hint)

    def refresh(self) -> None:
        overview = self.stats.overview()
        self.today_card.set_value(format_duration(overview.today_seconds, zero="0 分钟"))
        self.week_card.set_value(format_duration(overview.last7_seconds, zero="0 分钟"))
        self.total_card.set_value(format_duration(overview.total_seconds, zero="0 分钟"))
        daily = self.stats.daily_seconds(14)
        values = []
        for day_string, seconds in daily:
            day = date.fromisoformat(day_string)
            values.append((f"{day.month}/{day.day}", seconds))
        self.chart.set_data(values)
        self.chart_sum.setText(format_duration(sum(value for _, value in values), zero="0 分钟"))
        self._rebuild_rank()
        self.empty_hint.setVisible(not any(value for _, value in daily))
        self._rank_card_visible = bool(self._rank_rows)

    def _rebuild_rank(self) -> None:
        _clear_layout(self.rank_holder)
        self._rank_rows = 0
        ranking = self.stats.ranking(5)
        if not ranking:
            empty = QLabel("还没有排行数据")
            empty.setProperty("role", "muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(140)
            self.rank_holder.addWidget(empty)
            return
        maximum = max((total for _, total in ranking), default=1) or 1
        for index, (game, seconds) in enumerate(ranking):
            row = QWidget()
            layout = QVBoxLayout(row)
            layout.setContentsMargins(0, 5, 0, 5)
            layout.setSpacing(5)
            top = QHBoxLayout()
            top.setSpacing(8)
            rank = QLabel(str(index + 1))
            rank.setFixedWidth(18)
            rank.setStyleSheet(
                f"color: {'#B9A8FF' if index == 0 else COLORS['faint']}; "
                "font-size: 11px; font-weight: 700;"
            )
            top.addWidget(rank)
            icon_holder = GameIcon(30)
            icon_holder.set_game(game, self.library.icon_path(game))
            top.addWidget(icon_holder)
            name = QLabel(game.name)
            name.setProperty("role", "body")
            name.setToolTip(game.name)
            top.addWidget(name, 1)
            value = QLabel(format_duration(seconds, zero="0 分钟", compact=True))
            value.setProperty("role", "faint")
            top.addWidget(value)
            layout.addLayout(top)
            bar = RankBar(seconds / maximum, game.accent)
            layout.addWidget(bar)
            self.rank_holder.addWidget(row)
            self._rank_rows += 1

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()


# ---------------------------------------------------------------------------
class SettingsPage(ScrollPage):
    exportRequested = Signal()
    openDataRequested = Signal()

    def __init__(self, settings: SettingsStore, paths: AppPaths, autostart: AutostartManager) -> None:
        super().__init__()
        self.settings = settings
        self.paths = paths
        self.autostart = autostart
        self._build()

    def _section(self, title: str, subtitle: str = "") -> tuple[CardFrame, QVBoxLayout]:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(19, 16, 19, 16)
        layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setProperty("role", "h3")
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("role", "muted")
            sub.setWordWrap(True)
            layout.addWidget(sub)
        return card, layout

    def _build(self) -> None:
        self.content.addWidget(
            _page_header("设置", "调整游时的启动方式与数据管理。所有设置立即生效。")
        )

        launch_card, launch_layout = self._section("启动与托盘")
        self.close_toggle = ToggleRow(
            "关闭窗口时最小化到托盘",
            "关闭主窗口后继续在后台自动计时；从托盘菜单可以完全退出。",
            self.settings.get_bool("close_to_tray", True),
            icon_name="home",
        )
        self.close_toggle.changed.connect(self._close_changed)
        launch_layout.addWidget(self.close_toggle)
        launch_layout.addWidget(Separator())
        self.autostart_row = ToggleRow(
            "开机自动启动",
            "登录 Windows 后自动在托盘运行，只写入当前用户注册表，不需要管理员权限。",
            self.autostart.is_enabled(),
            icon_name="refresh",
        )
        self.autostart_row.changed.connect(self._autostart_changed)
        launch_layout.addWidget(self.autostart_row)
        launch_layout.addWidget(Separator())
        self.minimized_toggle = ToggleRow(
            "启动时直接最小化到托盘",
            "手动启动游时也直接进入托盘；开机自启始终使用托盘模式。",
            self.settings.get_bool("launch_minimized", False),
            icon_name="download",
        )
        self.minimized_toggle.changed.connect(
            lambda checked: self.settings.set_bool("launch_minimized", checked)
        )
        launch_layout.addWidget(self.minimized_toggle)
        self.content.addWidget(launch_card)

        record_card, record_layout = self._section("记录与通知")
        self.notify_toggle = ToggleRow(
            "开始计时时显示通知",
            "游戏进程被识别并开始计时后，发送一条 Windows 通知。",
            self.settings.get_bool("notify_game_started", False),
            icon_name="spark",
        )
        self.notify_toggle.changed.connect(
            lambda checked: self.settings.set_bool("notify_game_started", checked)
        )
        record_layout.addWidget(self.notify_toggle)
        record_layout.addWidget(Separator())
        info = QHBoxLayout()
        info.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(pixmap("clock", COLORS["green"], 17))
        info.addWidget(icon_label)
        text = QLabel(
            "自动计时只检测已添加游戏的 exe 进程，每 2 秒检查一次；电脑睡眠的间隔不会被计入时长。"
        )
        text.setProperty("role", "muted")
        text.setWordWrap(True)
        info.addWidget(text, 1)
        record_layout.addLayout(info)
        self.content.addWidget(record_card)

        data_card, data_layout = self._section("数据")
        path_row = QHBoxLayout()
        path_row.setSpacing(9)
        path_icon = QLabel()
        path_icon.setPixmap(pixmap("folder", COLORS["muted"], 16))
        path_row.addWidget(path_icon)
        self.path_label = QLabel(str(self.paths.root))
        self.path_label.setProperty("role", "body")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_row.addWidget(self.path_label, 1)
        open_button = SmallButton("打开目录", "external", variant="soft")
        open_button.clicked.connect(self.openDataRequested)
        path_row.addWidget(open_button)
        data_layout.addLayout(path_row)
        desc = QLabel("游戏、计时记录与图标保存在本机 SQLite 数据库中；游戏卸载后图标缓存仍会保留。")
        desc.setProperty("role", "muted")
        desc.setWordWrap(True)
        data_layout.addWidget(desc)
        data_layout.addWidget(Separator())
        export_row = QHBoxLayout()
        export_text = QVBoxLayout()
        export_text.setSpacing(2)
        title = QLabel("导出计时记录")
        title.setProperty("role", "h3")
        sub = QLabel("导出 UTF-8 CSV，可用 Excel 打开。")
        sub.setProperty("role", "muted")
        export_text.addWidget(title)
        export_text.addWidget(sub)
        export_row.addLayout(export_text, 1)
        export = SmallButton("导出 CSV", "download", variant="soft")
        export.clicked.connect(self.exportRequested)
        export_row.addWidget(export)
        data_layout.addLayout(export_row)
        self.content.addWidget(data_card)

        about_card, about_layout = self._section("关于")
        logo_row = QHBoxLayout()
        logo = QLabel()
        logo.setFixedSize(42, 42)
        logo.setPixmap(pixmap("gamepad", "#B9A8FF", 24))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: #221D3E; border-radius: 12px;")
        logo_row.addWidget(logo)
        about_text = QVBoxLayout()
        about_text.setSpacing(1)
        name = QLabel("游时 GameTime")
        name.setProperty("role", "h3")
        version = QLabel(f"版本 {__version__}")
        version.setProperty("role", "faint")
        about_text.addWidget(name)
        about_text.addWidget(version)
        logo_row.addLayout(about_text, 1)
        about_layout.addLayout(logo_row)
        description = QLabel(
            "一款本地优先的桌面游戏时光记录器。手动添加游戏，自动记录进程运行时长，"
            "数据只保存在你的电脑上。"
        )
        description.setProperty("role", "muted")
        description.setWordWrap(True)
        about_layout.addWidget(description)
        about_layout.addWidget(Separator())
        tech = QLabel("Python 3.14 · PySide6 / Qt 6.12 · SQLite · psutil · PyInstaller")
        tech.setProperty("role", "faint")
        tech.setWordWrap(True)
        about_layout.addWidget(tech)
        self.content.addWidget(about_card)
        self.content.addStretch(1)

    def refresh(self) -> None:
        self.close_toggle.switch.setChecked(self.settings.get_bool("close_to_tray", True))
        self.notify_toggle.switch.setChecked(self.settings.get_bool("notify_game_started", False))
        self.minimized_toggle.switch.setChecked(self.settings.get_bool("launch_minimized", False))
        self.autostart_row.switch.setChecked(self.autostart.is_enabled())
        self.path_label.setText(str(self.paths.root))

    def _close_changed(self, checked: bool) -> None:
        self.settings.set_bool("close_to_tray", checked)

    def _autostart_changed(self, checked: bool) -> None:
        try:
            self.autostart.set_enabled(checked)
            self.settings.set_bool("autostart", checked)
        except Exception as exc:
            self.autostart_row.switch.blockSignals(True)
            self.autostart_row.switch.setChecked(not checked)
            self.autostart_row.switch.blockSignals(False)
            show_message(self, "设置失败", f"无法写入开机自启设置：{exc}", danger=True)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()
