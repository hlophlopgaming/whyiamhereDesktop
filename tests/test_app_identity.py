import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from why_here.core import APP_ID, Engine, identity
from why_here.storage import installed_apps


class InstalledIdentityTest(unittest.TestCase):
	def test_desktop_suffix_is_part_of_id(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			(root / "applications").mkdir()
			(root / "applications/org.telegram.desktop.desktop").write_text(
				"[Desktop Entry]\nType=Application\nName=Telegram\nExec=Telegram\n"
			)
			with patch("why_here.storage.DATA", root), patch.dict("os.environ", {"XDG_DATA_DIRS": directory}):
				catalog = installed_apps()
			key = "desktop:org.telegram.desktop"
			self.assertEqual(catalog[key], "Telegram")
			engine = Engine(lambda: 10)
			engine.configure([key])
			windows = [
				{"id": "one", "desktop": "org.telegram.desktop"},
				{"id": "two", "desktop": "/opt/apps/org.telegram.desktop.desktop"},
				{"id": "other", "desktop": "org.telegram"},
			]
			self.assertEqual(engine.sync(windows), [key])
			self.assertEqual(engine.sessions[key].windows, {"one", "two"})
			self.assertEqual(engine.sync(windows), [])
			engine.start(key, "Тест", 1)
			engine.sessions[key].deadline = 10
			self.assertEqual(engine.tick()[1], [{"id": "one", "app": key}, {"id": "two", "app": key}])

	def test_absolute_paths_and_self_exclusion(self):
		self.assertEqual(identity({"desktop": "org.telegram.desktop"}), "desktop:org.telegram.desktop")
		self.assertEqual(identity({"desktop": "/opt/apps/firefox.desktop"}), "desktop:firefox")
		self.assertEqual(identity({"desktop": f"/opt/apps/{APP_ID}.desktop"}), "")
		self.assertEqual(identity({"desktop": APP_ID}), "")
