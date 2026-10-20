from __future__ import annotations


import pytest
from PySide6.QtWidgets import QLabel

from gametime.database import Database
from gametime.paths import AppPaths
from gametime.services.icons import IconService
from gametime.services.launcher import GameLauncher
from gametime.services.library import GameService
from gametime.services.processes import FakeProcessScanner
from gametime.services.scanner import ScanResult
from gametime.services.settings import AutostartManager, SettingsStore
from gametime.services.stats import StatsService
from gametime.services.tracking import TrackingEngine
from gametime.ui.dialogs import AddGameDialog, GameDetailDialog
from gametime.ui.dialogs_scan import ScanGamesDialog
from gametime.ui.main_window import MainWindow


@pytest.fixture
def services(paths: AppPaths, db: Database):
    icons = IconService(paths.icons)
    library = GameService(db, icons)
    stats = StatsService(db)
    scanner = FakeProcessScanner()
    tracker = TrackingEngine(db, library, scanner)
    settings = SettingsStore(db)
    return {
        "paths": paths,
        "db": db,
        "icons": icons,
        "library": library,
        "stats": stats,
        "tracker": tracker,
        "settings": settings,
        "scanner": scanner,
        "launcher": GameLauncher(),
    }


@pytest.fixture
def window(qapp, services):
    win = MainWindow(
        paths=services["paths"],
        db=services["db"],
        library=services["library"],
        stats=services["stats"],
        tracker=services["tracker"],
        settings=services["settings"],
        autostart=AutostartManager,
        launcher=services["launcher"],
        start_timers=False,
    )
    yield win
    win.hide()
    win.shutdown()
    win.deleteLater()
    qapp.processEvents()


def _all_label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_main_window_structure_and_navigation(qapp, window) -> None:
    window.show()
    qapp.processEvents()
    assert window.stack.count() == 4
    assert window.nav_buttons[0].isChecked()
    window._navigate(1)
    assert window.stack.currentIndex() == 1
    window._navigate(2)
    assert window.stack.currentIndex() == 2
    window._navigate(3)
    assert window.stack.currentIndex() == 3
    window._navigate(0)
    qapp.processEvents()
    assert window.dashboard.empty.isVisible() is True
    assert "游时" in window.windowTitle()


def test_add_game_dialog_saves_and_library_updates(
    qapp, window, services, exe_factory
) -> None:
    exe = exe_factory("dialog-game.exe")
    dialog = AddGameDialog(services["library"], services["icons"], parent=window)
    dialog.name_edit.setText("对话框游戏")
    dialog.path_edit.setText(str(exe))
    dialog.notes_edit.setText("备注")
    dialog._save()
    qapp.processEvents()
    assert dialog.saved_game is not None
    assert dialog.saved_game.name == "对话框游戏"
    assert dialog.result() == dialog.DialogCode.Accepted

    window.library_page.refresh()
    assert len(window.library_page._cards) == 1
    card = next(iter(window.library_page._cards.values()))
    assert "对话框游戏" in card.name_label.text()
    assert card.summary.missing is False
    dialog.close()
    dialog.deleteLater()
    qapp.processEvents()


def test_add_game_dialog_reports_duplicate(qapp, window, services, exe_factory) -> None:
    exe = exe_factory("dupe.exe")
    services["library"].add_game("原有", str(exe))
    dialog = AddGameDialog(services["library"], services["icons"], parent=window)
    dialog.name_edit.setText("重复")
    dialog.path_edit.setText(str(exe))
    dialog.show()
    qapp.processEvents()
    dialog._save()
    qapp.processEvents()
    assert dialog.saved_game is None
    assert dialog.error_label.isVisible()
    assert "已经" in dialog.error_label.text()
    dialog.close()
    dialog.deleteLater()
    qapp.processEvents()


def test_missing_game_uses_cached_metadata_and_never_unknown(
    qapp, window, services, exe_factory
) -> None:
    exe = exe_factory("will-vanish.exe")
    game = services["library"].add_game("会消失的游戏", str(exe))
    now = int(__import__("time").time())
    session_id = services["db"].start_session(game.id, "auto", now - 3600)
    services["db"].finish_session(
        session_id, duration_seconds=3600, ended_at=now
    )
    exe.unlink()

    window.library_page.refresh()
    card = window.library_page._cards[game.id]
    assert card.summary.missing is True
    assert card.status.text() == "文件缺失"
    assert card.status.isHidden() is False
    assert "历史记录已保留" in card.sub_label.text()
    assert "未知" not in card.name_label.text()

    detail = GameDetailDialog(
        game.id,
        services["library"],
        services["stats"],
        services["tracker"],
        services["launcher"],
        services["icons"],
        window,
    )
    detail.show()
    qapp.processEvents()
    assert detail.missing_badge.isVisible() is True
    assert detail.missing_banner.isVisible() is True
    assert detail.launch_button.text() == "重新定位游戏"
    texts = _all_label_texts(detail)
    assert not any("未知" in text for text in texts)
    assert any("不会用问号占位" in text for text in texts)
    detail.close()
    detail.deleteLater()
    qapp.processEvents()


def test_manual_timer_from_detail(qapp, window, services, exe_factory) -> None:
    game = services["library"].add_game("手动", str(exe_factory("manual-ui.exe")))
    detail = GameDetailDialog(
        game.id,
        services["library"],
        services["stats"],
        services["tracker"],
        services["launcher"],
        services["icons"],
        window,
    )
    detail.show()
    qapp.processEvents()
    detail._toggle_manual()
    qapp.processEvents()
    assert services["tracker"].active_source(game.id) == "manual"
    assert detail.manual_button.text() == "结束手动计时"
    detail._toggle_manual()
    qapp.processEvents()
    assert services["tracker"].active_source(game.id) is None
    assert detail.manual_button.text() == "开始手动计时"
    detail.close()
    detail.deleteLater()
    qapp.processEvents()


def test_delete_game_from_detail(
    qapp, window, services, exe_factory, monkeypatch
) -> None:
    game = services["library"].add_game("待删除", str(exe_factory("delete-ui.exe")))
    deleted: list[int] = []
    detail = GameDetailDialog(
        game.id,
        services["library"],
        services["stats"],
        services["tracker"],
        services["launcher"],
        services["icons"],
        window,
    )
    detail.deleted.connect(deleted.append)
    import gametime.ui.dialogs_confirm as confirm_module

    monkeypatch.setattr(confirm_module, "ask_confirm", lambda *args, **kwargs: True)
    detail.show()
    qapp.processEvents()
    detail._delete()
    qapp.processEvents()
    assert deleted == [game.id]
    with pytest.raises(Exception):
        services["library"].get_game(game.id)
    qapp.processEvents()


def test_stats_page_renders_data(qapp, services, exe_factory) -> None:
    library = services["library"]
    game = library.add_game("统计游戏", str(exe_factory("stats-ui.exe")))
    now = int(__import__("time").time())
    session_id = services["db"].start_session(game.id, "auto", now - 7200)
    services["db"].finish_session(
        session_id, duration_seconds=7200, ended_at=now
    )
    window = MainWindow(
        paths=services["paths"],
        db=services["db"],
        library=services["library"],
        stats=services["stats"],
        tracker=services["tracker"],
        settings=services["settings"],
        autostart=AutostartManager,
        launcher=services["launcher"],
        start_timers=False,
    )
    window.show()
    window._navigate(2)
    qapp.processEvents()
    assert len(window.stats_page.chart._values) == 14
    assert any(value > 0 for _, value in window.stats_page.chart._values)
    window.hide()
    window.shutdown()
    window.deleteLater()
    qapp.processEvents()


def test_settings_persist(qapp, window, services) -> None:
    window.settings_page.close_toggle.switch.setChecked(False)
    qapp.processEvents()
    assert services["settings"].get_bool("close_to_tray", True) is False
    window.settings_page.notify_toggle.switch.setChecked(True)
    qapp.processEvents()
    assert services["settings"].get_bool("notify_game_started", False) is True


def test_library_has_manual_and_scan_actions(qapp, window, services) -> None:
    window._navigate(1)
    assert window.library_page.scanRequested is not None
    window._navigate(0)
    assert window.dashboard.scanRequested is not None


def test_scan_dialog_can_add_selected_candidate(qapp, window, services, exe_factory) -> None:
    exe = exe_factory("scanned-game.exe")
    dialog = ScanGamesDialog(
        services["library"],
        parent=window,
        auto_start=False,
        initial_results=[
            ScanResult(
                exe_path=str(exe),
                display_name="扫描游戏",
                folder_name="扫描游戏",
                source="Steam",
                size_bytes=1_200_000,
            )
        ],
    )
    dialog.show()
    qapp.processEvents()
    assert dialog.full_scan_button.isChecked() is True
    assert len(dialog._rows) == 1
    assert dialog.add_button.isEnabled() is True
    dialog._add_selected()
    qapp.processEvents()
    assert dialog.added_count == 1
    assert any(item.game.name == "扫描游戏" for item in services["library"].list_games())
    dialog.close()
    dialog.deleteLater()
    qapp.processEvents()


def test_game_card_quick_action_launch_missing_opens_detail(
    qapp, window, services, exe_factory, monkeypatch
) -> None:
    exe = exe_factory("gone.exe")
    game = services["library"].add_game("已卸载", str(exe))
    exe.unlink()
    window.library_page.refresh()
    opened: list[int] = []
    monkeypatch.setattr(window, "open_detail", opened.append)
    window._quick_action(game.id)
    assert opened == [game.id]


def test_quick_action_launches_existing_game(
    qapp, window, services, exe_factory, monkeypatch
) -> None:
    from gametime.services.launcher import LaunchResult

    game = services["library"].add_game("启动测试", str(exe_factory("launch.exe")))
    calls: list[int] = []

    def fake_launch(g):
        calls.append(g.id)
        return LaunchResult(True, pid=1234)

    monkeypatch.setattr(services["launcher"], "launch", fake_launch)
    window._quick_action(game.id)
    assert calls == [game.id]


def test_launcher_reports_missing_file(services, exe_factory) -> None:
    game = services["library"].add_game("丢失", str(exe_factory("lost.exe")))
    game.path_obj.unlink()
    result = services["launcher"].launch(game)
    assert result.ok is False
    assert "重新定位" in result.error or "卸载" in result.error


def test_close_hides_to_tray_when_enabled(qapp, window, services) -> None:
    from PySide6.QtGui import QCloseEvent

    class FakeTray:
        def __init__(self) -> None:
            self.messages: list[tuple] = []

        def showMessage(self, *args) -> None:  # noqa: N802
            self.messages.append(args)

        def hide(self) -> None:
            pass

    tray = FakeTray()
    window.tray = tray
    services["settings"].set_bool("close_to_tray", True)
    window.show()
    qapp.processEvents()
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is False
    assert window.isHidden() is True
    assert len(tray.messages) == 1

    # 关闭托盘行为后应真正退出；避免触发 QApplication.quit，仅验证分支。
    services["settings"].set_bool("close_to_tray", False)
    window._force_quit = True
    assert window._cleaned is False
    window.shutdown()
    assert window._cleaned is True

