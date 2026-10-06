import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from why_here import storage


class GoalHistoryTest(unittest.TestCase):
	def test_recent_unique_goals_are_limited_and_persisted(self):
		settings = {"goals": {}}
		for number in range(12):
			storage.remember_goal(settings, "desktop:app", f" Goal {number} ")
		storage.remember_goal(settings, "desktop:app", "Goal 5")
		self.assertEqual(settings["goals"]["desktop:app"], ["Goal 5", *[f"Goal {number}" for number in range(11, 5, -1)], *[f"Goal {number}" for number in range(4, 1, -1)]])

		with TemporaryDirectory() as folder, patch.object(storage, "SETTINGS", Path(folder) / "settings.json"):
			storage.save_settings(storage.DEFAULTS | {"apps": {}, **settings})
			loaded, error = storage.read_settings()
			self.assertEqual(error, "")
			self.assertEqual(loaded["goals"], settings["goals"])
			self.assertEqual(json.loads(storage.SETTINGS.read_text())["goals"], settings["goals"])

	def test_autostart_without_installed_desktop_file(self):
		with TemporaryDirectory() as folder:
			root = Path(folder)
			with patch.object(storage, "AUTOSTART", root / "config/autostart/app.desktop"), patch.object(storage, "DATA", root / "data"), patch.object(storage.sys, "executable", "/tmp/Some Python"), patch.dict("os.environ", {"XDG_DATA_DIRS": str(root / "system-data")}):
				storage.set_autostart(True)
				content = storage.AUTOSTART.read_text()
				self.assertIn('Exec="/tmp/Some Python" "-m" "why_here" --background', content)
				storage.set_autostart(False)
				self.assertFalse(storage.AUTOSTART.exists())


if __name__ == "__main__":
	unittest.main()
