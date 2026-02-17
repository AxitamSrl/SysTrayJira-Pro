# SysTrayJira Pro

Premium version of [SysTrayJira](https://github.com/AxitamSrl/SysTrayJira) with advanced features.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Platform](https://img.shields.io/badge/platform-Linux%20|%20Windows%20|%20macOS-lightgrey)

## Pro Features

All features from the free version, plus:

- 🔔 Desktop notifications on new issues
- 🔢 Badge counter on tray icon
- ⚡ Quick status transitions (flat menu or zenity popup)
- 🔍 Search issues by key or text (zenity popup)
- 📋 Copy issue link to clipboard
- 🔗 Open Jira Board quick link
- 🕐 Time since last refresh + total issue count
- ⚙️ `max_results` and `sort_by` per group
- ✅ Config validation on load
- 📌 Current Tickets (Pinned) - Pin up to 2 tickets at the top
- ⚙️ Configuration popup - Zenity-based config editor
- 📝 Copy title - Copy ticket title to clipboard

## Compatibility

### Operating Systems

| OS | Version | Status |
|----|---------|--------|
| Ubuntu | 20.04+ | ✅ |
| Debian | 11+ | ✅ |
| Fedora | 36+ | ✅ |
| Arch Linux | Rolling | ✅ |
| Linux Mint | 20+ | ✅ |
| Windows | 10, 11 | ✅ |
| macOS | 10.14+ | ✅ |

### Desktop Environments (Linux)

| DE | Status | Notes |
|----|--------|-------|
| GNOME 3.x/40+ | ⚠️ | Requires [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/) |
| KDE Plasma | ✅ | Native tray support |
| XFCE | ✅ | Native tray support |
| Cinnamon | ✅ | Native tray support |
| MATE | ✅ | Native tray support |
| i3/Sway | ⚠️ | Needs a tray bar |

### Display Servers (Linux)

| Server | Status | Notes |
|--------|--------|-------|
| X11/Xorg | ✅ | Full support |
| Wayland | ⚠️ | Works with StatusNotifier/AppIndicator. GNOME Wayland needs the AppIndicator extension |

### Jira Compatibility

| Type | Status | Auth Mode |
|------|--------|-----------|
| Atlassian Cloud | ✅ | `basic` (email + API token) |
| Jira Server | ✅ | `bearer` or `pat` |
| Jira Data Center | ✅ | `bearer` or `pat` |

### Requirements

- Python 3.10+
- `zenity` (for popup transitions and search on Linux)

## Install

```bash
pip install git+https://github.com/AxitamSrl/SysTrayJira-Pro.git
```

### Linux dependencies

```bash
# Debian/Ubuntu
sudo apt install zenity xclip

# Fedora
sudo dnf install zenity xclip

# Arch
sudo pacman -S zenity xclip
```

## Quick Start

```bash
# 1. Generate default config
jira-tray-pro --init

# 2. Edit config
nano ~/.config/sysTrayJira/config.yaml

# 3. Set your token
export JIRA_API_TOKEN="your-token"

# 4. Run
jira-tray-pro
```

## Configuration

Config file: `~/.config/sysTrayJira/config.yaml`

### Full example

```yaml
jira_url: "https://your-jira-instance.com"
email: "your-email@example.com"
poll_interval: 300
auto_refresh: true
notifications: true

# Transition mode
#   "none"  — click opens issue in browser (default)
#   "flat"  — transitions listed as menu items under each group
#   "popup" — click ⚡ item opens a zenity dialog to pick a transition
transition_mode: "popup"

# Quick link to your Jira board (optional)
# board_url: "https://your-jira/secure/RapidBoard.jspa?rapidView=123"

# Custom tray icon (optional, PNG/ICO, supports ~)
# icon: "~/.config/sysTrayJira/jira.png"

# Bash-style .env file (optional, supports 'export' prefix)
# env_file: "~/.env"

# Auth
auth_mode: "bearer"         # basic | bearer | pat
token_env: "JIRA_API_TOKEN" # env var name for the token

# JQL groups
groups:
  - name: "🔥 Sprint"
    jql: "sprint = 54979 AND assignee = currentUser() AND resolution = Unresolved"
    active: true
    max_results: 20         # max issues to fetch (default: 20)
    sort_by: "priority"     # priority | status | key (default: priority)

  - name: "📋 My Open Issues"
    jql: "assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC"
    active: true

  - name: "👀 In Review"
    jql: "assignee = currentUser() AND status = 'In Review'"
    active: false           # hidden but kept in config
```

### Config Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `jira_url` | string | required | Jira instance base URL |
| `email` | string | required for `basic` | Email for basic auth |
| `poll_interval` | int | `300` | Auto-refresh interval (seconds) |
| `auto_refresh` | bool | `true` | Enable/disable auto-refresh |
| `notifications` | bool | `true` | Desktop notifications on new issues |
| `transition_mode` | string | `"none"` | `none`, `flat`, or `popup` |
| `board_url` | string | none | Quick link to Jira board |
| `icon` | string | none | Path to custom tray icon |
| `env_file` | string | none | Path to `.env` file |
| `auth_mode` | string | `"bearer"` | `basic`, `bearer`, or `pat` |
| `token_env` | string | `"JIRA_API_TOKEN"` | Env var name for the token |
| `groups[].name` | string | required | Display name (supports emoji) |
| `groups[].jql` | string | required | JQL query |
| `groups[].active` | bool | `true` | Show/hide group |
| `groups[].max_results` | int | `20` | Max issues to fetch |
| `groups[].sort_by` | string | `"priority"` | `priority`, `status`, or `key` |

### Auth Modes

| Mode | Description | Required fields |
|------|-------------|-----------------|
| `basic` | Email + API token (Atlassian Cloud) | `email` + `token_env` |
| `bearer` | Bearer token (Jira Server/DC) | `token_env` only |
| `pat` | Personal Access Token (Jira Server/DC) | `token_env` only |

### Transition Modes

| Mode | Behavior |
|------|----------|
| `none` | Click on issue opens it in browser. No transitions in menu. |
| `flat` | Click on issue opens browser. Transitions listed as `→ KEY: Action` items under each group. |
| `popup` | Click on issue opens browser. Separate `⚡` section with zenity popup per issue to pick a transition. |

### Priority Icons

| Emoji | Priorities |
|-------|-----------|
| 🔴 | Immediate, Blocker, Highest, 1=Must Have, P1 |
| 🟠 | Critical, High, 2=Should Have, P2 |
| 🟡 | Major, Medium, 3=Could Have, P3 |
| 🟢 | Minor, Low |
| 🔵 | Trivial, Lowest, Very Low, P4 |
| ⚪ | Unknown / Undefined |

## Pro Features Details

### 📌 Current Tickets (Pinned)

Pin up to 2 tickets as "current" to keep them at the top of the menu for easy access:

- Pinned tickets appear at the top of the tray menu with transitions and open-in-browser always visible
- Pin/Unpin tickets via the popup dialog when clicking on an issue
- Pinned tickets are stored in `~/.config/sysTrayJira/pinned.yaml` (internal file, not user-editable)
- Maximum of 2 tickets can be pinned at once

### ⚙️ Configuration Popup

Zenity-based configuration editor accessible from the tray menu:

- **Edit settings** - Opens the config file in your default editor
- **Manage groups** - Toggle groups active/inactive without editing YAML
- **Add group** - Create new JQL groups with guided prompts
- **Open config file** - Direct access to `config.yaml`

### 📝 Copy Title

In popup mode, you can copy the ticket title to clipboard:

- Format: `KEY — summary` (e.g., `PROJ-23871 — As a user I want to...`)
- Available in the popup dialog when clicking on an issue
- Uses system clipboard (requires `xclip` on Linux)

## Tray Menu

```
🕐 Last refresh: 2m ago (12 issues)
──────────────────────────────────────
── 📌 Current (2) ──
   🟡 PROJ-23871 — As a user... [In Progress]     ← pinned ticket
   🔴 PROJ-23309 — Critical bug... [In Progress]  ← pinned ticket
──────────────────────────────────────
── 🔥 Sprint (4) ──
   🟡 PROJ-23871 — As a user... [In Progress]     ← opens browser
   🟢 PROJ-23882 — Some task... [Open]
── 📋 My Open Issues (8) ──
   🔴 PROJ-23309 — Critical bug... [In Progress]
   ...
──────────────────────────────────────
⚡ Transitions ──                                  (popup mode only)
   ⚡ PROJ-23871 — As a user...                    ← zenity popup
   ⚡ PROJ-23882 — Some task...
──────────────────────────────────────
🔍 Search issues                                   ← zenity search
⚙️ Configuration                                   ← config popup
🔗 Open Jira Board                                 (if board_url set)
──────────────────────────────────────
Reload config
Refresh
Quit
──────────────────────────────────────
© Axitam SRL 1988-2026 — Apache 2.0
```

### Search (🔍)

1. Click "🔍 Search issues"
2. A zenity dialog asks for a search term (e.g. `1234` or `bug`)
3. Filters all loaded issues where key or summary contains the term (case-insensitive)
4. Results shown in a list — click one to open in browser

### Transitions (⚡)

1. Click on a `⚡ PROJ-XXXXX` item
2. A zenity dialog shows available transitions for that issue
3. Select one (e.g. "In Review") and it's applied immediately
4. Desktop notification confirms the transition

### Configuration (⚙️)

1. Click "⚙️ Configuration"
2. A zenity dialog shows configuration options:
   - **Edit settings** - Opens `config.yaml` in your default editor
   - **Manage groups** - Toggle groups active/inactive
   - **Add group** - Create new JQL groups with guided prompts
   - **Open config file** - Direct file access
3. Changes are applied immediately (no restart required)

## Run as a Service

### Linux (systemd)

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jira-tray-pro.service << EOF
[Unit]
Description=Jira System Tray Pro
After=graphical-session.target

[Service]
ExecStart=$(which jira-tray-pro)
Environment=DISPLAY=$DISPLAY
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now jira-tray-pro
```

Commands:

```bash
systemctl --user status jira-tray-pro
systemctl --user restart jira-tray-pro
systemctl --user stop jira-tray-pro
journalctl --user -u jira-tray-pro -f
```

### macOS (launchd)

```bash
cat > ~/Library/LaunchAgents/eu.axitam.jira-tray-pro.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>eu.axitam.jira-tray-pro</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which jira-tray-pro)</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/eu.axitam.jira-tray-pro.plist
```

### Windows (Startup)

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\JiraTrayPro.lnk")
$Shortcut.TargetPath = (Get-Command jira-tray-pro).Source
$Shortcut.Save()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tray icon not visible (GNOME) | Install `gnome-shell-extension-appindicator` |
| Tray icon not visible (i3/Sway) | Add tray to bar config |
| `KeyError: 'JIRA_API_TOKEN'` | Set env var or use `env_file` in config |
| `401 Unauthorized` | Check `auth_mode` matches your Jira type |
| `403 Forbidden` | Token lacks permissions |
| Priority icons all ⚪ | Custom priority names — check mapping |
| `str.removeprefix` error | Upgrade to Python 3.10+ |
| Transitions popup not showing | Install `zenity`, check `DISPLAY` env in service |
| Copy to clipboard not working | Install `xclip` or `xsel` |
| Service crashes on start | Check `DISPLAY` value: `echo $DISPLAY` |
| Configuration popup not opening | Install `zenity`, check `DISPLAY` env |
| Pinned tickets not persisting | Check write permissions to `~/.config/sysTrayJira/` |
| Copy title not working | Install `xclip` on Linux, check clipboard permissions |

## Free vs Pro

| Feature | Free | Pro |
|---------|------|-----|
| JQL groups + active toggle | ✅ | ✅ |
| Priority emojis | ✅ | ✅ |
| Auto/manual refresh | ✅ | ✅ |
| Multi-auth | ✅ | ✅ |
| .env file support | ✅ | ✅ |
| Click → browser | ✅ | ✅ |
| Reload config | ✅ | ✅ |
| Dynamic icon color | ✅ | ✅ |
| Custom icon | ✅ | ✅ |
| 🔔 Desktop notifications | ❌ | ✅ |
| 🔢 Badge counter | ❌ | ✅ |
| ⚡ Status transitions | ❌ | ✅ |
| 🔍 Search issues | ❌ | ✅ |
| 📋 Copy link to clipboard | ❌ | ✅ |
| 🔗 Jira Board link | ❌ | ✅ |
| 🕐 Last refresh time | ❌ | ✅ |
| ⚙️ max_results per group | ❌ | ✅ |
| ⚙️ sort_by per group | ❌ | ✅ |
| ✅ Config validation | ❌ | ✅ |
| 📌 Pinned/Current tickets | ❌ | ✅ |
| ⚙️ Config popup editor | ❌ | ✅ |
| 📝 Copy title | ❌ | ✅ |

## License

Copyright 1988-2026 Axitam SRL

Lead developer: Regis GILOT — regis.gilot@axitam.eu

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Support the Project

If you find SysTrayJira Pro useful, consider supporting its development:

- ⭐ Star the repo on GitHub
- 💖 [Sponsor on GitHub](https://github.com/sponsors/AxitamSrl) (USD)
- 💶 [Donate on Liberapay](https://fr.liberapay.com/Axitam) (EUR)

Your support helps keep this project alive and free for everyone!
