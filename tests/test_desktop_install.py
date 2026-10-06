import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "install-desktop.sh"


class DesktopInstallTest(unittest.TestCase):
	def test_install_and_invalid_executable(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			# Keep the test independent of the running KDE session.
			refresh = root / "kbuildsycoca6"
			refresh.write_text("#!/bin/sh\nexit 0\n")
			refresh.chmod(0o755)
			executable = root / 'Программа with spaces % " $ ` \\'
			executable.write_text("#!/bin/sh\nexit 0\n")
			executable.chmod(0o755)
			env = dict(os.environ, XDG_DATA_HOME=str(root / "data"), PATH=f"{root}:{os.environ['PATH']}")
			result = subprocess.run(["bash", str(SCRIPT), str(executable)], env=env, capture_output=True, text=True)
			self.assertEqual(result.returncode, 0, result.stderr)
			desktop = root / "data/applications/org.local.WhyHere.desktop"
			content = desktop.read_text()
			self.assertIn('Exec=/usr/bin/env -- "', content)
			self.assertIn('" --show\n', content)
			self.assertIn('%%', content)
			self.assertIn('\\\\"', content)
			self.assertIn('\\\\$', content)
			self.assertIn('\\\\`', content)
			self.assertIn('\\\\\\\\', content)
			result = subprocess.run(["bash", str(SCRIPT), str(root / "missing")], env=env, capture_output=True)
			self.assertNotEqual(result.returncode, 0)
			self.assertEqual(desktop.read_text(), content)
