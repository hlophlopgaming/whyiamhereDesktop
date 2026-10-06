#!/usr/bin/env python3
"""Build one Linux executable with the Python runtime, Qt and KWin script."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
	build = ROOT / "build"
	build.mkdir(exist_ok=True)
	entry = build / "entry.py"
	entry.write_text("from why_here.__main__ import main\nraise SystemExit(main())\n")
	subprocess.run([
		sys.executable, "-m", "PyInstaller",
		"--noconfirm", "--clean", "--onefile", "--name", "why-here",
		"--paths", str(ROOT),
		"--copy-metadata", "why-am-i-here-kde",
		"--add-data", f"{ROOT / 'why_here/kwin.js'}:why_here",
		"--add-data", f"{ROOT / 'why_here/assets'}:why_here/assets",
		"--distpath", str(ROOT / "dist"),
		"--workpath", str(build / "pyinstaller"),
		"--specpath", str(build),
		str(entry),
	], cwd=ROOT, check=True)
	print(f"Готово: {ROOT / 'dist/why-here'}")


if __name__ == "__main__":
	main()
