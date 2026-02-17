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


# ── Env & Config ──────────────────────────────────────────────

def load_env(path):
    """Load a bash-style .env file (supports 'export' prefix)."""
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
    """Validate config and print warnings."""
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
    """Send desktop notification (Linux: notify-send, macOS: osascript, Windows: toast)."""
    try:
        if os.name == "posix":
            if Path("/usr/bin/notify-send").exists():
                subprocess.run(["notify-send", title, body, "-i", "dialog-information"], timeout=5)
            elif Path("/usr/bin/osascript").exists():
                subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'], timeout=5)
        # Windows: fallback to print
    except Exception:
        pass


def detect_new_issues(old_data, new_data):
    """Return list of new issue keys per group."""
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
    # Badge with count
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
        # Notifications
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

    def _build_issue_submenu(self, issue):
        key = issue["key"].strip()
        items = [
            MenuItem("Open in browser", open_issue(self.cfg["jira_url"], key)),
            MenuItem("Copy link", self._make_copy_callback(key)),
            Menu.SEPARATOR,
        ]
        # Transitions
        try:
            transitions = get_transitions(self.cfg, key)
            for t in transitions:
                items.append(MenuItem(
                    f"→ {t['name']}",
                    self._make_transition_callback(key, t["id"], t["name"])
                ))
        except Exception:
            items.append(MenuItem("(transitions unavailable)", None, enabled=False))
        return Menu(*items)

    def build_menu(self):
        items = []
        # Refresh info
        if self.last_refresh:
            ago = datetime.datetime.now() - self.last_refresh
            mins = int(ago.total_seconds() // 60)
            refresh_txt = f"Last refresh: {mins}m ago" if mins > 0 else "Last refresh: just now"
        else:
            refresh_txt = "Not yet refreshed"
        items.append(MenuItem(f"🕐 {refresh_txt} ({self.total_count()} issues)", None, enabled=False))
        items.append(Menu.SEPARATOR)

        # Groups as submenus
        for g in self.cfg["groups"]:
            if not g.get("active", True):
                continue
            name = g["name"]
            issues = self.data.get(name, [])
            sort_by = g.get("sort_by", "priority")
            issues = sort_issues(issues, sort_by)

            if not issues:
                sub_items = [MenuItem("(empty)", None, enabled=False)]
            else:
                sub_items = []
                for i in issues:
                    key = i["key"].strip()
                    summary = i["fields"]["summary"][:50]
                    status = i["fields"]["status"]["name"]
                    priority = i["fields"].get("priority", {}).get("name", "")
                    picon = PRIORITY_ICONS.get(priority, "⚪")
                    label = f"{picon} {key} — {summary} [{status}]"
                    sub_items.append(MenuItem(label, self._build_issue_submenu(i)))

            items.append(MenuItem(f"{name} ({len(issues)})", Menu(*sub_items)))

        # Board link
        if self.cfg.get("board_url"):
            items.append(Menu.SEPARATOR)
            items.append(MenuItem("🔗 Open Jira Board", lambda *_: webbrowser.open(self.cfg["board_url"])))

        items.append(Menu.SEPARATOR)
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
