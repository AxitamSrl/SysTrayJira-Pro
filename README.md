# SysTrayJira Pro

Premium version of [SysTrayJira](https://github.com/AxitamSrl/SysTrayJira) with advanced features.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-Commercial-red)

## Pro Features

All features from the free version, plus:

- 🔔 Desktop notifications on new issues
- ⚡ Quick status transitions from tray menu
- 🔍 Quick search by issue key (popup)
- 📋 Copy issue link to clipboard
- 📂 Submenus per group
- 🔗 Open Jira Board quick link
- 🕐 Time since last refresh
- ⚙️ `max_results` and `sort_by` per group
- 🎨 Custom icon per group
- ✅ Config validation on load
- 👁️ Hot-reload config on file change

## Install

```bash
pip install git+https://github.com/AxitamSrl/SysTrayJira-Pro.git
```

## Quick Start

```bash
jira-tray-pro --init
nano ~/.config/sysTrayJira/config.yaml
export JIRA_API_TOKEN="your-token"
jira-tray-pro
```

## License

Copyright 1988-2026 Axitam SRL. All rights reserved.

This is proprietary software. A valid commercial license is required.

Contact: regis.gilot@axitam.eu
