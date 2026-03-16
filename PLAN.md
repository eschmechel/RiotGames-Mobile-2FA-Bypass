# Riot 2FA Bypass - Development Plan

## Status: v2.2.0 Development

---

## v2.2.0 Roadmap

### Phase 1: System Tray + Auto-start

**System Tray:**
- Add `QSystemTrayIcon` to `main_window.py`
- Minimize to tray on close (with setting to allow full exit)
- Right-click menu:
  - Show Window
  - Copy 2FA Code → (submenu with all accounts)
  - Settings submenu:
    - Minimize to tray on close (checkbox)
    - Start with Windows (checkbox)
  - Exit

**Auto-start:**
- Off by default
- Uses `winreg` to toggle `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Stored in config.json

---

### Phase 2: Account Search

- Search bar below header in `main_window.py`
- Real-time filtering as user types
- Case-insensitive name matching

---

### Phase 3: Desktop Notifications

- Only important events:
  - Code about to expire (5-second warning)
  - Account added
  - Account removed
- Off by default (user can enable in settings)

---

### Phase 4: i18n (Multi-language Support)

- Languages: English (default), Spanish, French
- JSON-based translation files in `app/i18n/`
- Language selector in Settings menu

---

### Phase 5: Documentation

- Update README.md with new features
- Add release notes
- Create CONTRIBUTING.md
- Update screenshots and video tutorial

---

## Dependencies

| Feature       | New dependency           | Notes                         |
| ------------- | ------------------------ | ----------------------------- |
| System tray   | PyQt6 (built-in)        | `QSystemTrayIcon`             |
| Auto-start    | `winreg` (built-in)     | Windows only                  |
| Search        | None                    | Built-in filtering            |
| Notifications | PyQt6 (built-in)        | `QSystemTrayIcon.showMessage()` |
| i18n          | JSON files              | Custom translation system     |

---

## Feature Priority

| Priority | Feature              |
| -------- | -------------------- |
| 1        | System Tray          |
| 2        | Auto-start           |
| 3        | Account Search       |
| 4        | Notifications        |
| 5        | i18n (EN/ES/FR)     |
| 6        | Documentation        |
