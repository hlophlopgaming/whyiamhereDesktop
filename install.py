#!/usr/bin/env python3
"""Per-user installer. No root, shell interpolation or system package changes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

APP_ID = "org.local.WhyHere"
SOURCE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
TARGET = DATA / "why-here"
DESKTOP = DATA / "applications" / (APP_ID + ".desktop")
ICON = DATA / "icons/hicolor/scalable/apps" / (APP_ID + ".svg")
AUTOSTART = CONFIG / "autostart" / (APP_ID + ".desktop")


def desktop_quote(value):
	# Desktop Entry Exec quoting, not shell quoting. Escape percent field codes.
	value = str(value).replace("%", "%%")
	for character in ('\\', '"', '`', '$'):
		value = value.replace(character, '\\' + character)
	return '"' + value.replace('\\', '\\\\') + '"'


def stop_running():
	qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
	if qdbus:
		subprocess.run([qdbus, APP_ID, "/Bridge", APP_ID + ".Quit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		subprocess.run([qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", APP_ID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
	parser = argparse.ArgumentParser(description="Установка и удаление «Зачем я здесь?» для текущего пользователя")
	parser.add_argument("--uninstall", action="store_true")
	parser.add_argument("--purge", action="store_true", help="при удалении удалить также настройки")
	args = parser.parse_args()
	if args.uninstall:
		stop_running()
		AUTOSTART.unlink(missing_ok=True)
		DESKTOP.unlink(missing_ok=True)
		ICON.unlink(missing_ok=True)
		if TARGET.exists():
			shutil.rmtree(TARGET)
		if args.purge:
			shutil.rmtree(CONFIG / "why-here", ignore_errors=True)
		print("Приложение, пункт меню, автозапуск и скрипт KWin удалены.")
		return
	if SOURCE == TARGET:
		raise SystemExit("Запустите установку из исходной папки проекта.")
	TARGET.mkdir(parents=True, exist_ok=True)
	venv = TARGET / ".venv"
	if not (venv / "bin/python").exists():
		subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
	python = venv / "bin/python"
	subprocess.run([str(python), "-m", "pip", "install", "-r", str(SOURCE / "requirements.txt")], check=True)
	stop_running()
	shutil.copytree(SOURCE / "why_here", TARGET / "why_here", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
	for name in ("README.md", "README.en.md", "TESTING.md", "LICENSE", "THIRD_PARTY.md", "requirements.txt", "install.py"):
		shutil.copy2(SOURCE / name, TARGET / name)
	launcher = TARGET / "launch.py"
	launcher.write_text("from why_here.__main__ import main\nraise SystemExit(main())\n")
	ICON.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(TARGET / "why_here/assets/icon.svg", ICON)
	DESKTOP.parent.mkdir(parents=True, exist_ok=True)
	DESKTOP.write_text(
		"[Desktop Entry]\nType=Application\nName=Why am I here?\nName[ru]=Зачем я здесь?\n"
		"Comment=Goals and time limits for your apps\nComment[ru]=Цель и время для ваших программ\n"
		f"Exec={desktop_quote(python)} {desktop_quote(launcher)} --show\n"
		f"Icon={APP_ID}\nTerminal=false\nCategories=Utility;\n"
		"StartupNotify=false\n"
	)
	if AUTOSTART.exists():
		AUTOSTART.write_text(DESKTOP.read_text().replace(" --show", " --background"))
	update = shutil.which("update-desktop-database")
	if update:
		subprocess.run([update, str(DESKTOP.parent)], check=False)
	print(f"Установлено. Найдите «Зачем я здесь?» в меню KDE.\nЗапуск: {python} {launcher}")


if __name__ == "__main__":
	main()
