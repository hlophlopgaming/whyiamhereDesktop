from .i18n import tr
from . import i18n
import configparser
import json
import os
from pathlib import Path
import sys

from .core import APP_ID

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
SETTINGS = CONFIG / "why-here/settings.json"
AUTOSTART = CONFIG / "autostart" / (APP_ID + ".desktop")
DEFAULTS = {"apps": {}, "goals": {}, "minutes": 15, "warning": 2, "sound": True, "opacity": 80, "enabled": True, "end_mode": "windows", "language": "ru"}


def remember_goal(settings, app, goal):
	goal = goal.strip()
	history = settings.setdefault("goals", {}).setdefault(app, [])
	history[:] = [goal, *(old for old in history if old != goal)][:10]


def read_settings():
	try:
		value = json.loads(SETTINGS.read_text())
		if not isinstance(value, dict):
			raise ValueError(tr("Ожидался объект настроек"))
		result = DEFAULTS | value
		if result["language"] not in ("ru", "en"):
			result["language"] = "ru"
		if result["end_mode"] not in ("windows", "kill"):
			result["end_mode"] = "windows"
		for key, low, high in (("minutes", 1, 1440), ("warning", 0, 1440), ("opacity", 25, 100)):
			result[key] = max(low, min(high, int(result[key])))
		if not isinstance(result["apps"], dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in result["apps"].items()):
			raise ValueError(tr("Неверный список программ"))
		result["apps"] = dict(result["apps"])
		goals = result.get("goals", {})
		if not isinstance(goals, dict):
			goals = {}
		result["goals"] = {}
		for app, history in goals.items():
			if not isinstance(app, str) or not isinstance(history, list):
				continue
			for goal in reversed(history):
				if isinstance(goal, str) and goal.strip():
					remember_goal(result, app, goal)
		return result, ""
	except FileNotFoundError:
		return DEFAULTS | {"apps": {}, "goals": {}}, ""
	except (ValueError, TypeError, OSError) as error:
		return DEFAULTS | {"apps": {}, "goals": {}}, tr("Не удалось прочитать настройки: {error}").format(error=error)


def save_settings(settings):
	SETTINGS.parent.mkdir(parents=True, exist_ok=True)
	temporary = SETTINGS.with_suffix(".tmp")
	temporary.write_text(json.dumps(settings, ensure_ascii=False, indent="\t") + "\n")
	temporary.chmod(0o600)
	temporary.replace(SETTINGS)


def set_autostart(enabled):
	if enabled:
		roots = [DATA, *map(Path, os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"))]
		source = next((root / "applications" / (APP_ID + ".desktop") for root in roots if (root / "applications" / (APP_ID + ".desktop")).exists()), None)
		AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
		if source:
			content = source.read_text().replace(" --show", " --background")
		else:
			arguments = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "why_here"]
			command = " ".join('"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"' for value in arguments)
			content = f"[Desktop Entry]\nType=Application\nName=Why am I here?\nExec={command} --background\nTerminal=false\n"
		AUTOSTART.write_text(content)
	else:
		AUTOSTART.unlink(missing_ok=True)


def installed_apps():
	roots = [DATA, *map(Path, os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")), Path.home() / ".local/share/flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
	seen, apps = set(), {}
	for root in roots:
		folder = root / "applications"
		for path in sorted(folder.rglob("*.desktop")) if folder.exists() else []:
			identifier = str(path.relative_to(folder)).replace("/", "-").removesuffix(".desktop")
			if identifier in seen or identifier == APP_ID:
				continue
			seen.add(identifier)
			parser = configparser.ConfigParser(interpolation=None, strict=False)
			try:
				parser.read(path, encoding="utf-8")
				entry = parser["Desktop Entry"]
				if entry.get("Type") != "Application" or entry.get("Hidden") == "true" or entry.get("NoDisplay") == "true":
					continue
				apps["desktop:" + identifier] = entry.get(f"Name[{i18n.LANGUAGE}]", entry.get("Name", identifier))
			except (configparser.Error, KeyError, UnicodeError, OSError):
				continue
	return apps
