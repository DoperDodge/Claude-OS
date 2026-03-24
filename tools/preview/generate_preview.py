#!/usr/bin/env python3
"""
Claude-OS Visual Preview Generator

Generates a self-contained HTML file that renders the Claude-OS UI
using the actual theme tokens and render data from all UI components.

Usage:
    python3 tools/preview/generate_preview.py [--screen lock|home|notifications|drawer]
    python3 tools/preview/generate_preview.py --all

Then open the generated HTML file in any browser.
"""

import argparse
import json
import os
import sys
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from ui.theme import get_theme, set_theme_mode, ThemeMode
from ui.compositor import Compositor, OutputConfig
from ui.lockscreen import LockScreen
from ui.lockscreen.lockscreen import LockScreenNotification
from ui.homescreen import HomeScreen
from ui.notifications import NotificationPanel, Notification
from ui.appdrawer import AppDrawer
from ui.statusbar.statusbar import StatusBar
from ui.keyboard.keyboard import OnScreenKeyboard


def collect_render_data(screen: str = "all") -> dict:
    """Collect render data from all UI components."""
    theme = get_theme()
    theme_data = theme.to_dict()

    # Status bar
    sb = StatusBar()
    sb._update_clock()
    sb.state.battery_level = 85
    sb.state.battery_charging = False
    sb.state.wifi_connected = True
    sb.state.wifi_ssid = "Home"
    sb.state.wifi_signal = 78
    sb.state.notification_count = 3
    sb._update_derived_state()

    # Lock screen
    ls = LockScreen()
    ls.add_notification(LockScreenNotification(
        app_name="Claude", title="Claude",
        body="I found the information you asked about earlier...",
        timestamp=time.time() - 120))
    ls.add_notification(LockScreenNotification(
        app_name="Messages", title="Alice",
        body="Hey, are you free for lunch tomorrow?",
        timestamp=time.time() - 300))

    # Home screen
    hs = HomeScreen()
    hs.update_badge("com.claude.messages", 3)
    hs.update_badge("com.claude.mail", 12)

    # Notification panel
    np = NotificationPanel()
    np.add_notification(Notification(
        id="1", app_name="Claude", title="Research Complete",
        body="I found what you asked about. Here's a summary of the key findings from the documents.",
        timestamp=time.time() - 120))
    np.add_notification(Notification(
        id="2", app_name="Messages", title="Alice",
        body="Hey, are you free for lunch tomorrow?",
        timestamp=time.time() - 300))
    np.add_notification(Notification(
        id="3", app_name="Mail", title="Weekly Report",
        body="Your weekly summary is ready to review.",
        timestamp=time.time() - 3600))
    np.show()

    # App drawer
    ad = AppDrawer()
    ad.show()

    # Keyboard
    kb = OnScreenKeyboard()
    kb.show()
    kb.update_suggestions(["hello", "help", "hey"])

    return {
        "theme": theme_data,
        "statusbar": sb.get_render_data(),
        "lockscreen": ls.get_render_data(),
        "homescreen": hs.get_render_data(),
        "notifications": np.get_render_data(),
        "appdrawer": ad.get_render_data(),
        "keyboard": kb.get_render_data(),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude-OS Visual Preview</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background: #1a1a2e;
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Display', sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding: 32px 16px;
    color: #fff;
}

h1 {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 8px;
    color: #E8D5C4;
}
.subtitle {
    font-size: 14px;
    color: #8E8E9E;
    margin-bottom: 24px;
}

.screen-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    flex-wrap: wrap;
    justify-content: center;
}
.screen-tabs button {
    padding: 8px 20px;
    border: 1px solid rgba(212,165,116,0.3);
    border-radius: 999px;
    background: rgba(255,255,255,0.05);
    color: #E8D5C4;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
}
.screen-tabs button:hover { background: rgba(212,165,116,0.15); }
.screen-tabs button.active {
    background: #D4A574;
    color: #1A1A2E;
    border-color: #D4A574;
    font-weight: 600;
}

.phone-frame {
    width: 375px;
    height: 812px;
    border-radius: 44px;
    overflow: hidden;
    position: relative;
    box-shadow: 0 0 0 3px #2a2a3e, 0 32px 80px rgba(0,0,0,0.5);
    flex-shrink: 0;
}

.screen { display: none; width: 100%; height: 100%; position: absolute; top: 0; left: 0; }
.screen.active { display: flex; flex-direction: column; }

/* ==================== STATUS BAR ==================== */
.statusbar {
    height: 54px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    font-size: 14px;
    font-weight: 600;
    z-index: 100;
    flex-shrink: 0;
    position: relative;
}
.statusbar-glass {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    backdrop-filter: blur(20px) saturate(1.8);
    -webkit-backdrop-filter: blur(20px) saturate(1.8);
    z-index: -1;
}
.statusbar .left { flex: 1; }
.statusbar .center {
    width: 120px; height: 32px;
    background: #1A1A2E; border-radius: 16px;
}
.statusbar .right {
    flex: 1; display: flex; align-items: center;
    justify-content: flex-end; gap: 6px; font-size: 12px; font-weight: 500;
}
.statusbar .badge {
    background: #D4A574; color: #fff; border-radius: 999px;
    padding: 1px 6px; font-size: 10px; font-weight: 700;
}
.wifi-icon, .battery-icon { font-size: 14px; }

/* ==================== LOCK SCREEN ==================== */
.lock-screen {
    background: linear-gradient(180deg, #1A1A2E 0%, #0F3460 100%);
}
.lock-clock {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; padding-bottom: 40px;
}
.lock-time {
    font-size: 72px; font-weight: 700; color: #FAF6F1;
    letter-spacing: 2px; line-height: 1;
}
.lock-date {
    font-size: 18px; font-weight: 500; color: #8E8E9E; margin-top: 8px;
}
.lock-notifications {
    padding: 0 16px; display: flex; flex-direction: column; gap: 8px;
    margin-bottom: 20px;
}
.lock-notif {
    background: rgba(255,255,255,0.12);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 12px 16px;
}
.lock-notif-app {
    font-size: 11px; font-weight: 600; color: #B8B8CC; margin-bottom: 4px;
}
.lock-notif-body {
    font-size: 13px; color: #E8D5C4; line-height: 1.4;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.lock-unlock-hint {
    text-align: center; padding: 16px 0 24px;
    display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.lock-indicator {
    width: 134px; height: 5px; border-radius: 3px;
    background: #D4A574; opacity: 0.6;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
.lock-hint-text { font-size: 12px; color: #8E8E9E; }

/* ==================== HOME SCREEN ==================== */
.home-screen { background: HOMESCREEN_BG; }
.home-content { flex: 1; overflow: hidden; }
.app-grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 0; padding: 20px 16px;
}
.app-item {
    display: flex; flex-direction: column; align-items: center;
    padding: 10px 0; cursor: pointer; position: relative;
}
.app-icon {
    width: 60px; height: 60px; border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; color: #fff; font-weight: 700;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    position: relative;
}
.app-icon .app-badge {
    position: absolute; top: -4px; right: -4px;
    background: #FF3B30; color: #fff; border-radius: 999px;
    min-width: 18px; height: 18px; font-size: 11px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    padding: 0 5px;
}
.app-label {
    font-size: 11px; margin-top: 6px; color: LABEL_COLOR;
    text-align: center; width: 100%;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.page-indicator {
    display: flex; justify-content: center; gap: 8px;
    padding: 8px 0;
}
.page-dot {
    width: 8px; height: 8px; border-radius: 4px; background: #E0D6CC;
}
.page-dot.active {
    width: 24px; background: #D4A574;
}
.dock {
    margin: 0 16px 8px;
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(20px) saturate(1.8);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 24px;
    display: flex; justify-content: space-around; align-items: center;
    padding: 12px 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.dock .app-icon { width: 52px; height: 52px; border-radius: 13px; font-size: 20px; }
.dock .app-item { padding: 0; }
.dock .app-label { display: none; }
.home-indicator {
    display: flex; justify-content: center; padding: 8px 0 6px;
}
.home-indicator-pill {
    width: 134px; height: 5px; border-radius: 3px;
    background: INDICATOR_COLOR; opacity: 0.3;
}

/* ==================== NOTIFICATIONS ==================== */
.notif-screen { background: rgba(26,26,46,0.95); }
.notif-content { flex: 1; overflow-y: auto; padding: 0 16px; }
.quick-settings {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 8px; margin: 16px 0;
}
.qs-toggle {
    background: #F5EDE4; border-radius: 16px;
    padding: 12px; text-align: center; cursor: pointer;
    transition: all 0.2s;
}
.qs-toggle.active { background: #D4A574; color: #fff; }
.qs-toggle .qs-icon { font-size: 20px; margin-bottom: 4px; }
.qs-toggle .qs-label { font-size: 11px; font-weight: 600; }
.qs-toggle .qs-sub { font-size: 10px; opacity: 0.7; margin-top: 2px; }
.brightness-slider {
    margin: 12px 0 20px; display: flex; align-items: center; gap: 10px;
}
.brightness-track {
    flex: 1; height: 28px; border-radius: 14px; background: #EDE3D8;
    position: relative; overflow: hidden;
}
.brightness-fill {
    height: 100%; border-radius: 14px; background: #D4A574;
    width: 80%;
}
.brightness-icon { font-size: 18px; color: #8E8E9E; }
.notif-header {
    display: flex; justify-content: space-between; align-items: center;
    margin: 8px 0 12px; padding: 0 4px;
}
.notif-header-title { font-size: 13px; color: #8E8E9E; font-weight: 600; }
.notif-header-clear { font-size: 13px; color: #D4A574; font-weight: 600; cursor: pointer; }
.notif-card {
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 16px; padding: 14px 16px;
    margin-bottom: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}
.notif-card-top {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 4px;
}
.notif-card-app { font-size: 11px; color: #8E8E9E; font-weight: 600; }
.notif-card-time { font-size: 11px; color: #8E8E9E; }
.notif-card-title { font-size: 15px; font-weight: 600; color: #1A1A2E; margin-bottom: 2px; }
.notif-card-body { font-size: 13px; color: #5A5A72; line-height: 1.4; }

/* ==================== APP DRAWER ==================== */
.drawer-screen { background: HOMESCREEN_BG; }
.drawer-handle {
    display: flex; justify-content: center; padding: 12px 0 8px;
}
.drawer-handle-bar {
    width: 40px; height: 4px; border-radius: 2px; background: #E0D6CC;
}
.drawer-search {
    margin: 8px 16px 16px;
    background: #F5EDE4; border-radius: 999px;
    padding: 10px 16px; font-size: 15px; color: #8E8E9E;
}
.drawer-content { flex: 1; overflow-y: auto; padding: 0 16px; }
.drawer-section-header {
    font-size: 15px; font-weight: 600; color: #8E8E9E;
    padding: 8px 0 4px;
}
.drawer-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
}

/* ==================== KEYBOARD ==================== */
.keyboard-container {
    flex-shrink: 0; padding: 4px 2px 8px;
    background: #D2CCC6;
}
.suggestion-bar {
    display: flex; height: 40px; align-items: center;
    border-bottom: 1px solid rgba(212,165,116,0.2);
    padding: 0 12px; gap: 0;
}
.suggestion-item {
    flex: 1; text-align: center; font-size: 15px; font-weight: 500;
    color: #1A1A2E; padding: 8px 0; cursor: pointer;
}
.suggestion-item + .suggestion-item {
    border-left: 1px solid rgba(212,165,116,0.3);
}
.kb-row { display: flex; justify-content: center; margin: 3px 0; gap: 3px; }
.kb-key {
    background: #fff; border-radius: 8px; height: 42px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; color: #1A1A2E; cursor: pointer;
    box-shadow: 0 1px 2px rgba(0,0,0,0.12);
    transition: transform 0.08s;
    flex-shrink: 0;
}
.kb-key:active { transform: scale(0.92); background: #D4A574; color: #fff; }
.kb-key.special {
    background: #B8B3AD; font-size: 14px; font-weight: 600;
}
</style>
</head>
<body>

<h1>Claude-OS Visual Preview</h1>
<p class="subtitle">Live render from design system tokens</p>

<div class="screen-tabs">
    <button class="active" onclick="showScreen('lock')">Lock Screen</button>
    <button onclick="showScreen('home')">Home</button>
    <button onclick="showScreen('notifications')">Notifications</button>
    <button onclick="showScreen('drawer')">App Drawer</button>
    <button onclick="showScreen('keyboard')">Keyboard</button>
</div>

<div class="phone-frame" id="phone">
    <!-- Screens are injected by JS -->
</div>

<script>
const DATA = __RENDER_DATA__;

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-' + name).classList.add('active');
    document.querySelectorAll('.screen-tabs button').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

function buildStatusBar(dark) {
    const sb = DATA.statusbar;
    const textColor = dark ? '#F5EDE4' : sb.left.time.color;
    const bgStyle = dark
        ? 'background: rgba(13,13,26,0.85);'
        : 'background: ' + sb.background.color + ';';
    return `
    <div class="statusbar" style="${bgStyle} color: ${textColor};">
        <div class="left">${sb.left.time.text}</div>
        <div class="center"></div>
        <div class="right">
            <span class="wifi-icon">&#9679;</span>
            <span>${sb.right.battery.level}%</span>
            ${sb.right.notifications.count > 0
                ? '<span class="badge">' + sb.right.notifications.count + '</span>' : ''}
        </div>
    </div>`;
}

function buildHomeIndicator(color, opacity) {
    return `<div class="home-indicator">
        <div class="home-indicator-pill" style="background:${color}; opacity:${opacity};"></div>
    </div>`;
}

function appIconLetter(name) {
    return name.charAt(0).toUpperCase();
}

function buildAppIcon(app, size) {
    size = size || 60;
    const radius = Math.round(size * 0.23);
    let badge = '';
    if (app.badge_count && app.badge_count > 0) {
        badge = `<div class="app-badge">${app.badge_count}</div>`;
    }
    return `<div class="app-item">
        <div class="app-icon" style="width:${size}px;height:${size}px;border-radius:${radius}px;background:${app.color};">
            ${appIconLetter(app.name)}${badge}
        </div>
        <div class="app-label">${app.name}</div>
    </div>`;
}

function buildLockScreen() {
    const ls = DATA.lockscreen;
    const notifs = ls.notifications.map(n => `
        <div class="lock-notif">
            <div class="lock-notif-app">${n.app_name}</div>
            <div class="lock-notif-body">${n.body}</div>
        </div>
    `).join('');

    return `<div id="screen-lock" class="screen lock-screen active">
        ${buildStatusBar(true)}
        <div class="lock-clock">
            <div class="lock-time">${ls.clock.time}</div>
            <div class="lock-date">${ls.clock.weekday}, ${ls.clock.date}</div>
        </div>
        <div class="lock-notifications">${notifs}</div>
        <div class="lock-unlock-hint">
            <div class="lock-indicator"></div>
            <div class="lock-hint-text">Swipe up to unlock</div>
        </div>
    </div>`;
}

function buildHomeScreen() {
    const hs = DATA.homescreen;
    const apps = hs.grid.apps.map(a => buildAppIcon(a)).join('');
    const dockApps = hs.dock.apps.map(a => buildAppIcon(a, 52)).join('');
    const dots = Array.from({length: hs.page_indicator.total}, (_, i) =>
        `<div class="page-dot ${i === hs.page_indicator.current ? 'active' : ''}"></div>`
    ).join('');

    return `<div id="screen-home" class="screen home-screen">
        ${buildStatusBar(false)}
        <div class="home-content">
            <div class="app-grid">${apps}</div>
            <div class="page-indicator">${dots}</div>
        </div>
        <div class="dock">${dockApps}</div>
        ${buildHomeIndicator('#1A1A2E', 0.3)}
    </div>`;
}

function buildNotifications() {
    const np = DATA.notifications;
    const toggles = np.quick_settings.toggles.map(t => `
        <div class="qs-toggle ${t.enabled ? 'active' : ''}">
            <div class="qs-icon">${t.icon === 'wifi' ? '&#9679;' : t.icon === 'bluetooth' ? 'B' : t.icon === 'moon' ? '&#9790;' : t.icon === 'flashlight' ? '&#9889;' : t.icon === 'rotate' ? '&#8635;' : '&#9789;'}</div>
            <div class="qs-label">${t.label}</div>
            ${t.subtitle ? '<div class="qs-sub">' + t.subtitle + '</div>' : ''}
        </div>
    `).join('');

    const cards = np.notifications_section.cards.map(n => `
        <div class="notif-card">
            <div class="notif-card-top">
                <span class="notif-card-app">${n.app_name}</span>
                <span class="notif-card-time">${n.time_ago}</span>
            </div>
            <div class="notif-card-title">${n.title}</div>
            <div class="notif-card-body">${n.body}</div>
        </div>
    `).join('');

    return `<div id="screen-notifications" class="screen notif-screen">
        ${buildStatusBar(true)}
        <div class="notif-content">
            <div class="quick-settings">${toggles}</div>
            <div class="brightness-slider">
                <span class="brightness-icon">&#9788;</span>
                <div class="brightness-track"><div class="brightness-fill"></div></div>
                <span class="brightness-icon">&#9728;</span>
            </div>
            <div class="notif-header">
                <span class="notif-header-title">Notifications</span>
                <span class="notif-header-clear">Clear</span>
            </div>
            ${cards}
        </div>
        ${buildHomeIndicator('#D4A574', 0.4)}
    </div>`;
}

function buildAppDrawer() {
    const ad = DATA.appdrawer;
    const sections = ad.grid.sections;
    let html = '';
    for (const [letter, section] of Object.entries(sections)) {
        html += `<div class="drawer-section-header">${letter}</div>`;
        html += '<div class="drawer-grid">';
        html += section.apps.map(a => buildAppIcon(a)).join('');
        html += '</div>';
    }

    return `<div id="screen-drawer" class="screen drawer-screen">
        ${buildStatusBar(false)}
        <div class="drawer-handle"><div class="drawer-handle-bar"></div></div>
        <div class="drawer-search">Search apps...</div>
        <div class="drawer-content">${html}</div>
        ${buildHomeIndicator('#1A1A2E', 0.3)}
    </div>`;
}

function buildKeyboardScreen() {
    const kb = DATA.keyboard;
    const suggestions = kb.suggestion_bar.suggestions.map(s =>
        `<div class="suggestion-item">${s}</div>`
    ).join('');

    const keyWidth = 34;
    const rows = kb.keys.rows.map(row => {
        const keys = row.map(k => {
            const w = Math.round(k.width * keyWidth);
            const cls = k.special ? 'kb-key special' : 'kb-key';
            return `<div class="${cls}" style="width:${w}px;">${k.label}</div>`;
        }).join('');
        return `<div class="kb-row">${keys}</div>`;
    }).join('');

    return `<div id="screen-keyboard" class="screen home-screen" style="justify-content:flex-end;">
        ${buildStatusBar(false)}
        <div style="flex:1; display:flex; align-items:center; justify-content:center;">
            <div style="background:#F5EDE4; border-radius:24px; padding:14px 20px; margin:0 32px; width:100%; max-width:311px;">
                <span style="color:#8E8E9E; font-size:16px;">Message Claude...</span>
            </div>
        </div>
        <div class="keyboard-container">
            <div class="suggestion-bar">${suggestions}</div>
            ${rows}
        </div>
        ${buildHomeIndicator('#1A1A2E', 0.3)}
    </div>`;
}

// Build all screens
document.getElementById('phone').innerHTML =
    buildLockScreen() +
    buildHomeScreen() +
    buildNotifications() +
    buildAppDrawer() +
    buildKeyboardScreen();
</script>
</body>
</html>"""


def generate_html(render_data: dict) -> str:
    """Generate the complete HTML preview."""
    theme = render_data["theme"]
    bg = theme["colors"]["background"]
    text_primary = theme["colors"]["text_primary"]

    html = HTML_TEMPLATE
    html = html.replace("__RENDER_DATA__", json.dumps(render_data, indent=2))
    html = html.replace("HOMESCREEN_BG", bg)
    html = html.replace("LABEL_COLOR", text_primary)
    html = html.replace("INDICATOR_COLOR", text_primary)
    return html


def main():
    parser = argparse.ArgumentParser(description="Claude-OS Visual Preview Generator")
    parser.add_argument("--output", "-o", default="preview.html",
                        help="Output HTML file path (default: preview.html)")
    args = parser.parse_args()

    print("[Claude-OS] Collecting render data from all UI components...")
    render_data = collect_render_data()

    output_path = os.path.join(PROJECT_ROOT, args.output)
    print(f"[Claude-OS] Generating HTML preview...")
    html = generate_html(render_data)

    with open(output_path, "w") as f:
        f.write(html)

    print(f"[Claude-OS] Preview saved to: {output_path}")
    print(f"[Claude-OS] Open in your browser to see the Visual OS!")


if __name__ == "__main__":
    main()
