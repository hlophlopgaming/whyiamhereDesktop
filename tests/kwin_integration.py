"""Real KDE test. Only freshly created org.local.WhyHereTest.* windows are closed."""
import json
import signal
import tempfile
from pathlib import Path
import subprocess
import sys
import time
import uuid

from PySide6.QtWidgets import QApplication
from why_here.core import APP_ID, Engine, clock, identity
from why_here.gui import Controller, GoalDialog
from why_here.processes import Processes
from PySide6.QtCore import ClassInfo, QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

CHILD = '''
import sys
from PySide6.QtWidgets import QApplication, QWidget
app = QApplication([])
app.setApplicationName(sys.argv[1])
app.setDesktopFileName(sys.argv[1])
app.setQuitOnLastWindowClosed(sys.argv[3] != "kill")
windows = [QWidget() for _ in range(int(sys.argv[2]))]
for w in windows:
	w.setWindowTitle("Зачем я здесь? — безопасное тестовое окно")
	w.resize(300, 100)
	w.show()
app.exec()
'''


SERVICE = "org.local.WhyHereTestProbe"
DISMISS = "--dismiss" in sys.argv
MODE = "kill" if "--kill" in sys.argv or DISMISS else "windows"


@ClassInfo(**{"D-Bus Interface": SERVICE})
class Probe(QObject):
	def __init__(self, app):
		super().__init__()
		self.app = app
		self.engine = Engine()
		self.processes = Processes()
		self.sent = []
		self.last_seen = 0
		self.stopping = False
		self.settings = {"end_mode": MODE, "minutes": 15}

	@Slot(str, str, result=str)
	def Exchange(self, token, payload):
		self.last_seen = clock()
		return json.dumps(self.snapshot(json.loads(payload)))

	def snapshot(self, windows):
		commands = Controller.snapshot(self, windows)
		self.sent.extend(command for command in commands if command.get("action") != "block")
		return commands

	def name(self, key):
		return "Тест закрытия формы"

	def goals(self, key):
		return []

	def dismiss_form(self, key):
		Controller.dismiss_form(self, key)

	def tick(self):
		pass

	def reconcile(self, added):
		pass

	def warn(self, warnings):
		pass


app = QApplication([])
app.setApplicationName(SERVICE)
app.setDesktopFileName(SERVICE)
probe = Probe(app)
bus = QDBusConnection.sessionBus()
assert bus.registerService(SERVICE), "Another integration test is running"
assert bus.registerObject("/Bridge", probe, QDBusConnection.ExportAllSlots)
scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus)
directory = tempfile.TemporaryDirectory(prefix="why-here-kwin-test-")
children = []


def wait_for(predicate, timeout=10):
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		app.processEvents()
		if predicate():
			return
		time.sleep(0.02)
	raise AssertionError("Истекло ожидание KWin")


try:
	path = Path(directory.name) / "test.js"
	path.write_text(Path("why_here/kwin.js").read_text().replace(APP_ID, SERVICE))
	reply = scripting.call("loadScript", str(path), SERVICE)
	assert reply.type() != QDBusMessage.ErrorMessage, reply.errorMessage()
	number = int(reply.arguments()[0])
	assert number >= 0
	script = QDBusInterface("org.kde.KWin", f"/Scripting/Script{number}", "org.kde.kwin.Script", bus)
	reply = script.call("run")
	assert reply.type() != QDBusMessage.ErrorMessage, reply.errorMessage()
	wait_for(lambda: probe.last_seen > 0)
	suffix = uuid.uuid4().hex[:8]
	chosen, other = [f"org.local.WhyHereTest.{suffix}.{part}.desktop" for part in ("Chosen", "Other")]
	for identifier, count in ((chosen, 2), (other, 1)):
		children.append(subprocess.Popen([sys.executable, "-c", CHILD, identifier, str(count), MODE]))
	key = "desktop:" + chosen
	probe.engine.configure([key])
	wait_for(lambda: key in probe.engine.sessions and len(probe.engine.sessions[key].windows) == 2)
	wait_for(lambda: any(identity(w) == "desktop:" + other for w in probe.engine.windows.values()))
	wait_for(lambda: all(w.get("minimized") for w in probe.engine.windows.values() if identity(w) == key))
	print("KWin blocked and minimized two selected windows; the control window survived", flush=True)
	if DISMISS:
		form = GoalDialog(probe, key)
		form.show()
		wait_for(lambda: any(w.get("promptActive") for w in probe.engine.windows.values()))
		form.close()
		assert probe.engine.sessions[key].goal == ""
	else:
		probe.engine.start(key, "Завершить только тестовую программу", 1, MODE)
		wait_for(lambda: all(not w.get("minimized") for w in probe.engine.windows.values() if identity(w) == key))
		probe.engine.finish(key)
	wait_for(lambda: children[0].poll() is not None)
	wait_for(lambda: key not in probe.engine.sessions)
	assert children[1].poll() is None, "Control window was closed!"
	if MODE == "kill":
		assert children[0].returncode == -signal.SIGKILL
		assert not probe.sent
		print("PASS: KWin PID → SIGKILL; resident test app exited; control survived", flush=True)
	else:
		assert len(probe.sent) == 2 and all(c["app"] == key for c in probe.sent)
		print("PASS: two closeWindow requests; control survived; session removed", flush=True)
finally:
	scripting.call("unloadScript", SERVICE)
	bus.unregisterObject("/Bridge")
	bus.unregisterService(SERVICE)
	directory.cleanup()
	probe.processes.close()
	# Clean up only the child processes created by this test.
	for child in children:
		if child.poll() is None:
			child.terminate()
		child.wait(timeout=5)
