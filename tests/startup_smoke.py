"""Exercise the real demo entry point; startup must not open a goal form."""
import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from why_here.__main__ import main
from why_here.gui import GoalDialog, SettingsWindow


def check_startup():
	app = QApplication.instance()
	app.processEvents()
	windows = app.topLevelWidgets()
	assert any(isinstance(w, SettingsWindow) and w.isVisible() for w in windows)
	assert not any(isinstance(w, GoalDialog) for w in windows)
	window = next(w for w in windows if isinstance(w, SettingsWindow))
	assert not window.controller.engine.sessions
	window.controller.new_demo()
	app.processEvents()
	assert any(isinstance(w, GoalDialog) and w.isVisible() for w in app.topLevelWidgets())
	window.controller.cleanup()
	print("Demo startup: no automatic form; explicit demo button still opens form")
	return 0


with patch.object(sys, "argv", ["why-here", "--demo"]), patch.object(QApplication, "exec", side_effect=check_startup):
	assert main() == 0
