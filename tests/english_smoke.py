"""Check the English GUI, icons and safe demo actions without touching real apps."""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from why_here.gui import Controller

app = QApplication([])
c = Controller(app, demo=True, language="en")
c.show_settings()
assert c.window.windowTitle() == "Why am I here?"
assert not app.windowIcon().pixmap(32, 32).isNull()
assert c.tray.toolTip() == "Why am I here?"
assert c.menu.actions()[0].text() == "Open settings"
c.new_demo()
app.processEvents()
key = "desktop:demo1"
assert c.forms[key].windowTitle() == "Why am I here? — Demo application 1"
assert c.forms[key].goal.placeholderText() == "For example: reply to an email"
c.start_session(key, "Write tomorrow's plan", 15)
assert c.reminders[key].windowTitle() == "Why am I here? — reminder"
assert c.reminders[key].finish_button.text() == "End session now"
assert "Write tomorrow's plan" in c.reminders[key].label.text()
assert c.reminders[key].windowFlags() & Qt.WindowDoesNotAcceptFocus
c.window.grab().save("artifacts/settings-en.png")
c.reminders[key].grab().save("artifacts/reminder-en.png")
QTest.mouseClick(c.reminders[key].finish_button, Qt.LeftButton)
assert c.demo_closes == 1
assert "simulated closures" in c.window.status.text()
c.window.language.setCurrentIndex(c.window.language.findData("ru"))
assert c.settings["language"] == "ru"
assert c.window.windowTitle() == "Why am I here?", "Language change must wait for restart"
c.cleanup()
print("English GUI, icons, tray and demo: OK")
