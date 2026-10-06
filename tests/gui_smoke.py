"""Run with QT_QPA_PLATFORM=offscreen; no KWin or real window closure."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QPushButton
from why_here.gui import Controller

app = QApplication([])
c = Controller(app, demo=True)
c.new_demo()
app.processEvents()
key = "desktop:demo1"
assert key in c.forms
assert not any(b.text() == "Позже" for b in c.forms[key].findChildren(QPushButton))
c.forms[key].reject()
assert c.engine.sessions[key].deadline is None
c.show_pending()
assert c.forms[key].isVisible()
c.start_session(key, "Проверка GUI", 1)
assert c.reminders[key].windowFlags() & Qt.WindowDoesNotAcceptFocus
c.advance_demo(False)
assert c.engine.sessions[key].warned
assert c.reminders[key].effective_opacity == 1.0
QTest.mouseClick(c.reminders[key].finish_button, Qt.LeftButton)
assert c.engine.sessions[key].ended_manually
assert not c.reminders[key].finish_button.isEnabled()
assert c.demo_closes == 1
c.advance_demo(True)
assert c.demo_closes == 1
c.window.end_mode.setCurrentIndex(c.window.end_mode.findData("kill"))
c.new_demo()
app.processEvents()
c.start_session("desktop:demo2", "Демо SIGKILL", 5)
with patch.object(c.processes, "kill") as kill:
	QTest.mouseClick(c.reminders["desktop:demo2"].finish_button, Qt.LeftButton)
	kill.assert_not_called()
assert c.engine.sessions["desktop:demo2"].end_mode == "kill"
for action in ("close", "escape"):
	c.new_demo()
	app.processEvents()
	pending = f"desktop:demo{c.demo_number}"
	before = c.demo_closes
	with patch.object(c.processes, "kill") as kill:
		if action == "close":
			c.forms[pending].close()
		else:
			QTest.keyClick(c.forms[pending], Qt.Key_Escape)
		kill.assert_not_called()
	assert c.demo_closes == before + 1
	assert c.engine.sessions[pending].expired
	assert pending not in c.reminders
c.new_demo()
app.processEvents()
before = c.demo_closes
c.set_enabled(False)
app.processEvents()
assert not c.engine.sessions
assert c.demo_closes == before
c.set_enabled(True)
app.processEvents()
c.new_demo()
app.processEvents()
pending = f"desktop:demo{c.demo_number}"
c.cleanup()
c.forms[pending].close()
assert c.engine.sessions[pending].deadline is None
c.cleanup()
print("GUI smoke: OK")
