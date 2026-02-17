#!/usr/bin/env python3
# Copyright 1988-2026 Axitam SRL. All rights reserved.
# Proprietary — Commercial license required.
# Lead developer: Regis GILOT <regis.gilot@axitam.eu>
import os, time, threading, webbrowser, subprocess, datetime
import requests, yaml
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "sysTrayJira" / "config.yaml"
PINNED_PATH = Path.home() / ".config" / "sysTrayJira" / "pinned.yaml"
MAX_PINNED = 2


# ── Pinned (Current Tickets) ─────────────────────────────────

def load_pinned():
    if PINNED_PATH.exists():
        with open(PINNED_PATH) as f:
            return yaml.safe_load(f) or []
    return []


def save_pinned(pinned):
    PINNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PINNED_PATH, "w") as f:
        yaml.dump(pinned[:MAX_PINNED], f, allow_unicode=True)


def pin_ticket(key):
    pinned = load_pinned()
    if key not in pinned:
        pinned.insert(0, key)
        pinned = pinned[:MAX_PINNED]
    save_pinned(pinned)


def unpin_ticket(key):
    pinned = load_pinned()
    pinned = [k for k in pinned if k != key]
    save_pinned(pinned)


# ── Env & Config ──────────────────────────────────────────────

def load_env(path):
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ")
            key, _, val = line.partition("=")
            if key and val:
                os.environ.setdefault(key, val.strip('"').strip("'"))


def validate_config(cfg):
    errors = []
    if not cfg.get("jira_url"):
        errors.append("jira_url is required")
    if cfg.get("auth_mode") == "basic" and not cfg.get("email"):
        errors.append("email is required for basic auth")
    if not cfg.get("groups"):
        errors.append("at least one group is required")
    for i, g in enumerate(cfg.get("groups", [])):
        if not g.get("name"):
            errors.append(f"groups[{i}]: name is required")
        if not g.get("jql"):
            errors.append(f"groups[{i}]: jql is required")
    for e in errors:
        print(f"⚠️  Config warning: {e}")
    return len(errors) == 0


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    if "env_file" in cfg:
        load_env(Path(cfg["env_file"]).expanduser())
    validate_config(cfg)
    return cfg


# ── Auth & API ────────────────────────────────────────────────

def get_auth(cfg):
    token = os.environ[cfg.get("token_env", "JIRA_API_TOKEN")]
    mode = cfg.get("auth_mode", "bearer")
    if mode == "basic":
        return {"auth": (cfg["email"], token)}
    if mode in ("bearer", "pat"):
        return {"headers": {"Authorization": f"Bearer {token}"}}
    raise ValueError(f"Unknown auth_mode: {mode}")


def fetch_issues(cfg, jql, max_results=20):
    r = requests.get(
        f"{cfg['jira_url']}/rest/api/2/search",
        params={"jql": jql, "maxResults": max_results, "fields": "summary,status,priority,key"},
        **get_auth(cfg),
    )
    r.raise_for_status()
    return r.json()["issues"]


def transition_issue(cfg, key, transition_id):
    r = requests.post(
        f"{cfg['jira_url']}/rest/api/2/issue/{key}/transitions",
        json={"transition": {"id": transition_id}},
        **get_auth(cfg),
    )
    r.raise_for_status()


def get_transitions(cfg, key):
    r = requests.get(
        f"{cfg['jira_url']}/rest/api/2/issue/{key}/transitions",
        **get_auth(cfg),
    )
    r.raise_for_status()
    return r.json()["transitions"]


# ── Notifications ─────────────────────────────────────────────

def notify(title, body):
    try:
        if os.name == "posix":
            if Path("/usr/bin/notify-send").exists():
                subprocess.run(["notify-send", title, body, "-i", "dialog-information"], timeout=5)
            elif Path("/usr/bin/osascript").exists():
                subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'], timeout=5)
    except Exception:
        pass


def detect_new_issues(old_data, new_data):
    new_issues = []
    for group, issues in new_data.items():
        old_keys = {i["key"] for i in old_data.get(group, [])}
        for i in issues:
            if i["key"] not in old_keys:
                new_issues.append((group, i))
    return new_issues


# ── Clipboard ─────────────────────────────────────────────────

def copy_to_clipboard(text):
    try:
        if os.name == "posix":
            for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["pbcopy"]):
                try:
                    subprocess.run(cmd, input=text.encode(), timeout=5, check=True)
                    return
                except FileNotFoundError:
                    continue
    except Exception:
        pass


# ── Zenity Transition Dialog ──────────────────────────────────

def show_transition_dialog(cfg, key, summary):
    """Show a zenity dialog with available transitions + open in browser."""
    try:
        transitions = get_transitions(cfg, key)
        pinned = load_pinned()
        pin_label = "📌 Unpin from current" if key in pinned else "📌 Pin as current"
        choices = ["🌐 Open in browser", "📋 Copy link", "📝 Copy title", pin_label]
        choices += [f"→ {t['name']}" for t in transitions]
        if not transitions:
            choices.append("(no transitions available)")

        result = subprocess.run(
            ["zenity", "--list", "--title", f"⚡ {key}",
             "--text", f"{key} — {summary[:60]}",
             "--column", "Action", *choices,
             "--width", "400", "--height", "350"],
            capture_output=True, text=True, timeout=60,
            env=_zenity_env()
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        selected = result.stdout.strip()
        if selected == "🌐 Open in browser":
            webbrowser.open(f"{cfg['jira_url']}/browse/{key}")
        elif selected == "📋 Copy link":
            copy_to_clipboard(f"{cfg['jira_url']}/browse/{key}")
            notify("Copied", f"{key} link copied to clipboard")
        elif selected == "📝 Copy title":
            copy_to_clipboard(f"{key} — {summary}")
            notify("Copied", f"{key} title copied to clipboard")
        elif selected == "📌 Pin as current":
            pin_ticket(key)
            notify("Pinned", f"{key} set as current ticket")
        elif selected == "📌 Unpin from current":
            unpin_ticket(key)
            notify("Unpinned", f"{key} removed from current tickets")
        else:
            tname = selected.removeprefix("→ ")
            for t in transitions:
                if t["name"] == tname:
                    transition_issue(cfg, key, t["id"])
                    notify("Transition OK", f"{key} → {tname}")
                    return
    except Exception as e:
        notify("Transition error", str(e))


def show_search_dialog(cfg, data):
    """Show a zenity entry dialog to filter issues by key/text."""
    try:
        result = subprocess.run(
            ["zenity", "--entry", "--title", "Search issues",
             "--text", "Enter issue key or text to filter:",
             "--width", "400"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")}
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        query = result.stdout.strip().lower()
        matches = []
        for issues in data.values():
            for i in issues:
                key = i["key"]
                summary = i["fields"]["summary"]
                if query in key.lower() or query in summary.lower():
                    matches.append(f"{key}|{summary[:60]}|{i['fields']['status']['name']}")
        if not matches:
            subprocess.run(["zenity", "--info", "--text", f"No issues matching '{query}'", "--width", "300"],
                           timeout=10, env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")})
            return
        result = subprocess.run(
            ["zenity", "--list", "--title", f"Results for '{query}'",
             "--text", f"{len(matches)} matches",
             "--column", "Key", "--column", "Summary", "--column", "Status",
             *[field for m in matches for field in m.split("|")],
             "--width", "600", "--height", "400", "--print-column", "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")}
        )
        if result.returncode == 0 and result.stdout.strip():
            selected_key = result.stdout.strip()
            webbrowser.open(f"{cfg['jira_url']}/browse/{selected_key}")
    except Exception as e:
        notify("Search error", str(e))


def _zenity_env():
    return {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")}


def show_config_dialog():
    """Show zenity dialogs to edit config."""
    try:
        cfg = load_config()
        env = _zenity_env()

        # Main action choice
        result = subprocess.run(
            ["zenity", "--list", "--title", "⚙️ Configuration",
             "--text", "Choose an action:",
             "--column", "Action",
             "Edit settings", "Manage groups", "Add group", "Open config file",
             "--width", "400", "--height", "300"],
            capture_output=True, text=True, timeout=60, env=env
        )
        if result.returncode != 0 or not result.stdout.strip():
            return

        action = result.stdout.strip()

        if action == "Edit settings":
            _edit_settings(cfg, env)
        elif action == "Manage groups":
            _manage_groups(cfg, env)
        elif action == "Add group":
            _add_group(cfg, env)
        elif action == "Open config file":
            subprocess.Popen(["xdg-open", str(CONFIG_PATH)], env=env)
            return

    except Exception as e:
        notify("Config error", str(e))


def _edit_settings(cfg, env):
    result = subprocess.run(
        ["zenity", "--forms", "--title", "⚙️ Edit Settings",
         "--text", "Modify settings (leave blank to keep current):",
         "--add-entry", f"Jira URL [{cfg.get('jira_url', '')}]",
         "--add-entry", f"Email [{cfg.get('email', '')}]",
         "--add-entry", f"Poll interval secs [{cfg.get('poll_interval', 300)}]",
         "--add-combo", "Auto refresh",
         "--combo-values", "true|false",
         "--add-combo", "Notifications",
         "--combo-values", "true|false",
         "--add-combo", "Transition mode",
         "--combo-values", "none|flat|popup",
         "--add-combo", "Auth mode",
         "--combo-values", "basic|bearer|pat",
         "--add-entry", f"Token env var [{cfg.get('token_env', 'JIRA_API_TOKEN')}]",
         "--add-entry", f"Board URL [{cfg.get('board_url', '')}]",
         "--width", "500", "--height", "450"],
        capture_output=True, text=True, timeout=120, env=env
    )
    if result.returncode != 0 or not result.stdout.strip():
        return

    vals = result.stdout.strip().split("|")
    if len(vals) >= 9:
        if vals[0]: cfg["jira_url"] = vals[0]
        if vals[1]: cfg["email"] = vals[1]
        if vals[2]: cfg["poll_interval"] = int(vals[2])
        if vals[3]: cfg["auto_refresh"] = vals[3] == "true"
        if vals[4]: cfg["notifications"] = vals[4] == "true"
        if vals[5]: cfg["transition_mode"] = vals[5]
        if vals[6]: cfg["auth_mode"] = vals[6]
        if vals[7]: cfg["token_env"] = vals[7]
        if vals[8]: cfg["board_url"] = vals[8]
        _save_config(cfg)
        notify("Config saved", "Settings updated. Click 'Reload config' to apply.")


def _manage_groups(cfg, env):
    groups = cfg.get("groups", [])
    rows = []
    for g in groups:
        rows.extend([g["name"], g["jql"][:60], str(g.get("active", True))])

    result = subprocess.run(
        ["zenity", "--list", "--title", "📋 Manage Groups",
         "--text", "Select a group to toggle active/inactive:",
         "--column", "Name", "--column", "JQL", "--column", "Active",
         *rows,
         "--width", "700", "--height", "400", "--print-column", "1"],
        capture_output=True, text=True, timeout=60, env=env
    )
    if result.returncode != 0 or not result.stdout.strip():
        return

    selected = result.stdout.strip()
    for g in groups:
        if g["name"] == selected:
            g["active"] = not g.get("active", True)
            _save_config(cfg)
            state = "active" if g["active"] else "inactive"
            notify("Group toggled", f"{selected} is now {state}. Reload config to apply.")
            return


def _add_group(cfg, env):
    result = subprocess.run(
        ["zenity", "--forms", "--title", "➕ Add Group",
         "--text", "New JQL group:",
         "--add-entry", "Name (e.g. 🔥 My Group)",
         "--add-entry", "JQL query",
         "--add-entry", "Max results (default: 20)",
         "--add-combo", "Sort by",
         "--combo-values", "priority|status|key",
         "--width", "500", "--height", "300"],
        capture_output=True, text=True, timeout=120, env=env
    )
    if result.returncode != 0 or not result.stdout.strip():
        return

    vals = result.stdout.strip().split("|")
    if len(vals) >= 2 and vals[0] and vals[1]:
        new_group = {
            "name": vals[0],
            "jql": vals[1],
            "active": True,
        }
        if len(vals) >= 3 and vals[2]:
            new_group["max_results"] = int(vals[2])
        if len(vals) >= 4 and vals[3]:
            new_group["sort_by"] = vals[3]
        cfg.setdefault("groups", []).append(new_group)
        _save_config(cfg)
        notify("Group added", f"{vals[0]} added. Reload config to apply.")


def _save_config(cfg):
    # Remove env_file loaded vars from cfg before saving
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── Icons & Priorities ────────────────────────────────────────

PRIORITY_COLORS = {
    "Immediate": "#cc0000", "Blocker": "#cc0000", "Highest": "#EC3536", "1=Must Have": "#EC3536", "P1": "#EC3536",
    "Critical": "#ff0000", "High": "#ff0000", "2=Should Have": "#F29328", "P2": "#F6BC17",
    "Major": "#009900", "Medium": "#ff9900", "3=Could Have": "#F6BC17", "P3": "#F7E402",
    "Minor": "#006600", "Low": "#33cc00",
    "Trivial": "#003300", "Lowest": "#003300", "Very Low": "#003300", "P4": "#00A3DD",
}

PRIORITY_ICONS = {
    "Immediate": "🔴", "Blocker": "🔴", "Highest": "🔴", "1=Must Have": "🔴", "P1": "🔴",
    "Critical": "🟠", "High": "🟠", "2=Should Have": "🟠", "P2": "🟠",
    "Major": "🟡", "Medium": "🟡", "3=Could Have": "🟡", "P3": "🟡",
    "Minor": "🟢", "Low": "🟢",
    "Trivial": "🔵", "Lowest": "🔵", "Very Low": "🔵", "4 = Won\u2019t Have": "🔵", "P4": "🔵",
    "Undefined": "⚪", "Standard": "⚪",
}

PRIORITY_ORDER = [
    "Immediate", "Blocker", "Highest", "1=Must Have", "P1",
    "Critical", "High", "2=Should Have", "P2",
    "Major", "Medium", "3=Could Have", "P3",
    "Minor", "Low",
    "Trivial", "Lowest", "Very Low", "P4",
]


def make_icon(color="blue", icon_path=None, count=0):
    if icon_path and Path(icon_path).exists():
        img = Image.open(icon_path).resize((64, 64)).convert("RGBA")
    else:
        img = Image.new("RGBA", (64, 64), color)
        d = ImageDraw.Draw(img)
        d.rectangle([8, 8, 56, 56], fill=color)
        d.text((22, 14), "J", fill="white")
    if count > 0:
        d = ImageDraw.Draw(img)
        d.ellipse([38, 0, 63, 25], fill="red")
        txt = str(count) if count < 100 else "99+"
        d.text((44, 3), txt, fill="white")
    return img


def get_highest_priority(data):
    for p in PRIORITY_ORDER:
        for issues in data.values():
            for i in issues:
                if i["fields"].get("priority", {}).get("name") == p:
                    return p
    return None


def open_issue(url, key):
    def _open(*_args):
        webbrowser.open(f"{url}/browse/{key}")
    return _open


def sort_issues(issues, sort_by="priority"):
    if sort_by == "priority":
        return sorted(issues, key=lambda i: PRIORITY_ORDER.index(i["fields"].get("priority", {}).get("name", "")) if i["fields"].get("priority", {}).get("name", "") in PRIORITY_ORDER else 999)
    elif sort_by == "status":
        return sorted(issues, key=lambda i: i["fields"]["status"]["name"])
    elif sort_by == "key":
        return sorted(issues, key=lambda i: i["key"])
    return issues


# ── Main App ──────────────────────────────────────────────────

class JiraTray:
    def __init__(self):
        self.cfg = load_config()
        self.data = {}
        self.icon = None
        self.last_refresh = None

    def total_count(self):
        return sum(len(v) for v in self.data.values())

    def fetch_all(self):
        old_data = dict(self.data)
        for g in self.cfg["groups"]:
            if not g.get("active", True):
                continue
            try:
                max_r = g.get("max_results", 20)
                self.data[g["name"]] = fetch_issues(self.cfg, g["jql"], max_r)
            except Exception as e:
                self.data[g["name"]] = []
                print(f"Error fetching '{g['name']}': {e}")
        self.last_refresh = datetime.datetime.now()
        if old_data and self.cfg.get("notifications", True):
            new = detect_new_issues(old_data, self.data)
            for group, issue in new:
                key = issue["key"]
                summary = issue["fields"]["summary"][:60]
                notify(f"New issue in {group}", f"{key} — {summary}")

    def _make_transition_callback(self, key, tid, tname):
        def _cb(*_args):
            try:
                transition_issue(self.cfg, key, tid)
                notify("Transition OK", f"{key} → {tname}")
                self.refresh()
            except Exception as e:
                notify("Transition failed", str(e))
        return _cb

    def _make_copy_callback(self, key):
        def _cb(*_args):
            copy_to_clipboard(f"{self.cfg['jira_url']}/browse/{key}")
        return _cb

    def _make_gtk_transition_callback(self, key, summary):
        def _cb(*_args):
            threading.Thread(target=show_transition_dialog, args=(self.cfg, key, summary), daemon=True).start()
        return _cb

    def _make_unpin_callback(self, key):
        def _cb(*_args):
            unpin_ticket(key)
            notify("Unpinned", f"{key} removed from current tickets")
            self.refresh()
        return _cb

    def _make_config_callback(self):
        def _cb(*_args):
            def _run():
                show_config_dialog()
                self.reload()
            threading.Thread(target=_run, daemon=True).start()
        return _cb

    def _make_search_callback(self):
        def _cb(*_args):
            threading.Thread(target=show_search_dialog, args=(self.cfg, self.data), daemon=True).start()
        return _cb

    def _get_issue_transitions(self, key):
        """Fetch transitions for an issue, cached."""
        try:
            return get_transitions(self.cfg, key)
        except Exception:
            return []

    def build_menu(self):
        items = []
        transition_mode = self.cfg.get("transition_mode", "none")

        # Refresh info
        if self.last_refresh:
            ago = datetime.datetime.now() - self.last_refresh
            mins = int(ago.total_seconds() // 60)
            refresh_txt = f"Last refresh: {mins}m ago" if mins > 0 else "Last refresh: just now"
        else:
            refresh_txt = "Not yet refreshed"
        items.append(MenuItem(f"🕐 {refresh_txt} ({self.total_count()} issues)", None, enabled=False))
        items.append(Menu.SEPARATOR)

        # Pinned / Current tickets
        pinned_keys = load_pinned()
        if pinned_keys:
            items.append(MenuItem("── 📌 Current ──", None, enabled=False))
            all_issues = {i["key"]: i for issues in self.data.values() for i in issues}
            for pk in pinned_keys:
                if pk in all_issues:
                    i = all_issues[pk]
                    summary = i["fields"]["summary"][:50]
                    status = i["fields"]["status"]["name"]
                    priority = i["fields"].get("priority", {}).get("name", "")
                    picon = PRIORITY_ICONS.get(priority, "⚪")
                    label = f"   📌 {picon} {pk} — {summary} [{status}]"
                    items.append(MenuItem(label, open_issue(self.cfg["jira_url"], pk)))
                    items.append(MenuItem(f"      📌 Unpin", self._make_unpin_callback(pk)))
                    # Always show transitions under pinned tickets
                    for t in self._get_issue_transitions(pk):
                        items.append(MenuItem(
                            f"      → {t['name']}",
                            self._make_transition_callback(pk, t["id"], t["name"])
                        ))
                else:
                    items.append(MenuItem(f"   📌 {pk} (not in current results)", open_issue(self.cfg["jira_url"], pk)))
            items.append(Menu.SEPARATOR)

        for g in self.cfg["groups"]:
            if not g.get("active", True):
                continue
            name = g["name"]
            issues = self.data.get(name, [])
            sort_by = g.get("sort_by", "priority")
            issues = sort_issues(issues, sort_by)

            items.append(MenuItem(f"── {name} ({len(issues)}) ──", None, enabled=False))
            if not issues:
                items.append(MenuItem("   (empty)", None, enabled=False))
            for i in issues:
                key = i["key"].strip()
                summary = i["fields"]["summary"][:50]
                status = i["fields"]["status"]["name"]
                priority = i["fields"].get("priority", {}).get("name", "")
                picon = PRIORITY_ICONS.get(priority, "⚪")
                label = f"   {picon} {key} — {summary} [{status}]"

                if transition_mode == "popup":
                    label += " ⚡"
                    items.append(MenuItem(label, self._make_gtk_transition_callback(key, summary)))
                else:
                    items.append(MenuItem(label, open_issue(self.cfg["jira_url"], key)))

                # Flat: transitions right under each ticket
                if transition_mode == "flat":
                    for t in self._get_issue_transitions(key):
                        items.append(MenuItem(
                            f"      → {t['name']}",
                            self._make_transition_callback(key, t["id"], t["name"])
                        ))

        # Board link

        # Board link
        if self.cfg.get("board_url"):
            items.append(Menu.SEPARATOR)
            items.append(MenuItem("🔗 Open Jira Board", lambda *_: webbrowser.open(self.cfg["board_url"])))

        items.append(Menu.SEPARATOR)
        items.append(MenuItem("🔍 Search issues", self._make_search_callback()))
        items.append(MenuItem("⚙️ Configuration", self._make_config_callback()))
        items.append(MenuItem("Reload config", lambda _, __: self.reload()))
        items.append(MenuItem("Refresh", lambda _, __: self.refresh()))
        items.append(MenuItem("Quit", lambda icon, _: icon.stop()))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("© Axitam SRL 1988-2026 — Commercial License", lambda *_: webbrowser.open("https://www.axitam.eu")))
        return Menu(*items)

    def update_icon(self):
        icon_path = self.cfg.get("icon")
        if icon_path:
            icon_path = str(Path(icon_path).expanduser())
        priority = get_highest_priority(self.data)
        color = PRIORITY_COLORS.get(priority, "blue")
        if self.icon:
            self.icon.icon = make_icon(color, icon_path, self.total_count())

    def refresh(self):
        self.fetch_all()
        if self.icon:
            self.update_icon()
            self.icon.menu = self.build_menu()

    def reload(self):
        self.cfg = load_config()
        self.refresh()

    def poll(self):
        while True:
            time.sleep(self.cfg.get("poll_interval", 300))
            if self.cfg.get("auto_refresh", True):
                self.refresh()

    def run(self):
        self.fetch_all()
        priority = get_highest_priority(self.data)
        color = PRIORITY_COLORS.get(priority, "blue")
        icon_path = self.cfg.get("icon")
        if icon_path:
            icon_path = str(Path(icon_path).expanduser())
        self.icon = Icon("jira-tray-pro", make_icon(color, icon_path, self.total_count()), "Jira Issues Pro", self.build_menu())
        threading.Thread(target=self.poll, daemon=True).start()
        self.icon.run()


# ── Config init & CLI ─────────────────────────────────────────

DEFAULT_CONFIG = """\
jira_url: "https://your-jira-instance.com"
email: "your-email@example.com"
poll_interval: 300
auto_refresh: true
notifications: true

# Transition mode: "none" (click opens browser), "flat" (transitions listed in menu), "popup" (GTK dialog)
transition_mode: "none"

# board_url: "https://your-jira-instance.com/secure/RapidBoard.jspa?rapidView=123"

# Custom icon (optional, path to PNG/ICO file)
# icon: "~/.config/sysTrayJira/jira.png"

# Env file (bash-style with 'export' supported)
# env_file: "~/.env"

# Auth mode: "basic" (email + token), "bearer" (token only), "pat" (Personal Access Token)
auth_mode: "bearer"
# Env var name containing the token
token_env: "JIRA_API_TOKEN"

groups:
  - name: "📋 My Open Issues"
    jql: "assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC"
    active: true
    max_results: 20
    sort_by: "priority"   # priority | status | key
"""


def init_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        print(f"Config already exists: {CONFIG_PATH}")
        return
    CONFIG_PATH.write_text(DEFAULT_CONFIG)
    print(f"Config created: {CONFIG_PATH}")
    print("Edit it with your Jira URL, email, and JQL groups.")


def main():
    import sys
    if "--init" in sys.argv:
        init_config()
        return
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}")
        print("Run 'jira-tray-pro --init' to create a default config.")
        sys.exit(1)
    JiraTray().run()


if __name__ == "__main__":
    main()
