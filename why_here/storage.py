from .i18n import tr
from . import i18n
import configparser
import json
import os
from pathlib import Path

from .core import APP_ID

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
SETTINGS = CONFIG / "why-here/settings.json"
AUTOSTART = CONFIG / "autostart" / (APP_ID + ".desktop")
DEFAULTS = {"apps": {}, "minutes": 15, "warning": 2, "sound": True, "opacity": 80, "enabled": True, "end_mode": "windows", "language": "ru"}


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
		return result, ""
	except FileNotFoundError:
		return DEFAULTS | {"apps": {}}, ""
	except (ValueError, TypeError, OSError) as error:
		return DEFAULTS | {"apps": {}}, tr("Не удалось прочитать настройки: {error}").format(error=error)


def save_settings(settings):
	SETTINGS.parent.mkdir(parents=True, exist_ok=True)
	temporary = SETTINGS.with_suffix(".tmp")
	temporary.write_text(json.dumps(settings, ensure_ascii=False, indent="\t") + "\n")
	temporary.chmod(0o600)
	temporary.replace(SETTINGS)


def set_autostart(enabled):
	if enabled:
		source = DATA / "applications" / (APP_ID + ".desktop")
		if not source.exists():
			raise OSError(tr("Сначала выполните установку: python3 install.py"))
		AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
		AUTOSTART.write_text(source.read_text().replace(" --show", " --background"))
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
