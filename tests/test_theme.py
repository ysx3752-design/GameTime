from __future__ import annotations

import gametime.ui.main_window as main_window_module
import gametime.ui.theme as theme


def test_palette_and_system_following(monkeypatch, qapp) -> None:
    monkeypatch.setattr(theme, "_is_system_dark", lambda: False)
    assert theme.set_theme("system") == "light"
    assert theme.is_dark_active() is False
    assert theme.COLORS["bg"] == theme.COLORS_LIGHT["bg"]
    assert theme.COLORS["bg"] in theme.build_stylesheet()

    monkeypatch.setattr(theme, "_is_system_dark", lambda: True)
    assert theme.set_theme("system") == "dark"
    assert theme.is_dark_active() is True

    assert theme.set_theme("light") == "light"
    assert theme.effective_theme() == "light"
    assert theme.set_theme("unknown") == "dark"


def test_main_window_switches_theme_and_rebuilds(qapp, window, services) -> None:
    window._apply_theme_mode("light", notify=False)
    qapp.processEvents()
    assert services["settings"].get("theme_mode") == "light"
    assert theme.effective_theme() == "light"
    assert window.stack.count() == 4
    assert window.settings_page.theme_selector.current_mode() == "light"
    assert theme.COLORS["bg"] in qapp.styleSheet()

    window._apply_theme_mode("dark", notify=False)
    qapp.processEvents()
    assert services["settings"].get("theme_mode") == "dark"
    assert theme.effective_theme() == "dark"
    assert window.stack.count() == 4


def test_follow_system_watcher_applies_light(monkeypatch, qapp, window, services) -> None:
    services["settings"].set("theme_mode", "system")
    monkeypatch.setattr(theme, "_is_system_dark", lambda: False)
    monkeypatch.setattr(main_window_module, "system_theme", lambda: "light")
    window._watch_system_theme()
    qapp.processEvents()
    assert theme.effective_theme() == "light"
    assert services["settings"].get("theme_mode") == "system"
    assert window.stack.count() == 4
