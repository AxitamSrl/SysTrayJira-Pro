#!/usr/bin/env python3
# Copyright 1988-2026 Axitam SRL
# Licensed under the Apache License, Version 2.0
# Lead developer: Regis GILOT <regis.gilot@axitam.eu>
import os, time, threading, webbrowser
import requests, yaml
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "sysTrayJira" / "config.yaml"


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


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    if "env_file" in cfg:
        load_env(Path(cfg["env_file"]).expanduser())
    return cfg


def get_auth(cfg):
    token = os.environ[cfg.get("token_env", "JIRA_API_TOKEN")]
    mode = cfg.get("auth_mode", "bearer")
    if mode == "basic":
        return {"auth": (cfg["email"], token)}
    elif mode == "bearer":
        return {"headers": {"Authorization": f"Bearer {token}"}}
    elif mode == "pat":
        return {"headers": {"Authorization": f"Bearer {token}"}}
    raise ValueError(f"Unknown auth_mode: {mode}")


def fetch_issues(cfg, jql):
    r = requests.get(
        f"{cfg['jira_url']}/rest/api/2/search",
        params={"jql": jql, "maxResults": 20, "fields": "summary,status,priority"},
        **get_auth(cfg),
    )
    r.raise_for_status()
    return r.json()["issues"]


PRIORITY_COLORS = {
    "Immediate": "#cc0000", "Blocker": "#cc0000", "Highest": "#EC3536", "1=Must Have": "#EC3536", "P1": "#EC3536",
    "Critical": "#ff0000", "High": "#ff0000", "2=Should Have": "#F29328", "P2": "#F6BC17",
    "Major": "#009900", "Medium": "#ff9900", "3=Could Have": "#F6BC17", "P3": "#F7E402",
    "Minor": "#006600", "Low": "#33cc00",
    "Trivial": "#003300", "Lowest": "#003300", "Very Low": "#003300", "P4": "#00A3DD",
}


def make_icon(color="blue", icon_path=None):
    if icon_path and Path(icon_path).exists():
        return Image.open(icon_path).resize((64, 64)).convert("RGBA")
    img = Image.new("RGBA", (64, 64), color)
    d = ImageDraw.Draw(img)
    # Draw a bigger "J" centered
    d.rectangle([8, 8, 56, 56], fill=color)
    d.text((22, 14), "J", fill="white")
    return img


def get_highest_priority(data):
    order = ["Highest", "High", "Medium", "Low", "Lowest"]
    for p in order:
        for issues in data.values():
            for i in issues:
                if i["fields"].get("priority", {}).get("name") == p:
                    return p
    return None


PRIORITY_ICONS = {
    "Immediate": "🔴", "Blocker": "🔴", "Highest": "🔴", "1=Must Have": "🔴", "P1": "🔴",
    "Critical": "🟠", "High": "🟠", "2=Should Have": "🟠", "P2": "🟠",
    "Major": "🟡", "Medium": "🟡", "3=Could Have": "🟡", "P3": "🟡",
    "Minor": "🟢", "Low": "🟢",
    "Trivial": "🔵", "Lowest": "🔵", "Very Low": "🔵", "4 = Won\u2019t Have": "🔵", "P4": "🔵",
    "Undefined": "⚪", "Standard": "⚪",
}


def open_issue(url, key):
    def _open(*_args):
        webbrowser.open(f"{url}/browse/{key}")
    return _open


class JiraTray:
    def __init__(self):
        self.cfg = load_config()
        self.data = {}
        self.icon = None

    def fetch_all(self):
        for g in self.cfg["groups"]:
            if not g.get("active", True):
                continue
            try:
                self.data[g["name"]] = fetch_issues(self.cfg, g["jql"])
            except Exception as e:
                self.data[g["name"]] = []
                print(f"Error fetching '{g['name']}': {e}")

    def build_menu(self):
        items = []
        for g in self.cfg["groups"]:
            if not g.get("active", True):
                continue
            name = g["name"]
            issues = self.data.get(name, [])
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
                items.append(MenuItem(label, open_issue(self.cfg["jira_url"], key)))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Reload config", lambda _, __: self.reload()))
        items.append(MenuItem("Refresh", lambda _, __: self.refresh()))
        items.append(MenuItem("Quit", lambda icon, _: icon.stop()))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("© Axitam SRL 1988-2026 — Apache 2.0", lambda *_: webbrowser.open("https://www.axitam.eu")))
        return Menu(*items)

    def update_icon(self):
        icon_path = self.cfg.get("icon")
        if icon_path:
            icon_path = str(Path(icon_path).expanduser())
        priority = get_highest_priority(self.data)
        color = PRIORITY_COLORS.get(priority, "blue")
        if self.icon:
            self.icon.icon = make_icon(color, icon_path)

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
        self.icon = Icon("jira-tray", make_icon(color, icon_path), "Jira Issues", self.build_menu())
        threading.Thread(target=self.poll, daemon=True).start()
        self.icon.run()


DEFAULT_CONFIG = """\
jira_url: "https://your-jira-instance.com"
email: "your-email@example.com"
poll_interval: 300
auto_refresh: true

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
        print("Run 'jira-tray --init' to create a default config.")
        sys.exit(1)
    JiraTray().run()


if __name__ == "__main__":
    main()
