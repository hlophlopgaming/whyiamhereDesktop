from .i18n import tr
import json
import secrets
import tempfile
from pathlib import Path

from PySide6.QtCore import ClassInfo, QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from .core import APP_ID, clock


@ClassInfo(**{"D-Bus Interface": APP_ID})
class Bridge(QObject):
	def __init__(self, controller):
		super().__init__(controller)
		self.controller = controller
		self.token = secrets.token_hex(24)
		self.last_seen = 0
		self.bus = QDBusConnection.sessionBus()
		self.directory = None
		self.scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", self.bus)

	@Slot(str, str, result=str)
	def Exchange(self, token, payload):
		if token != self.token:
			return "[]"
		try:
			windows = json.loads(payload)
			if not isinstance(windows, list) or not all(isinstance(w, dict) and isinstance(w.get("id"), str) for w in windows):
				return "[]"
		except (ValueError, TypeError):
			return "[]"
		self.last_seen = clock()
		return json.dumps(self.controller.snapshot(windows))

	@Slot()
	def Show(self):
		self.controller.show_settings()

	@Slot()
	def Quit(self):
		self.controller.app.quit()

	def start(self):
		if not self.bus.registerService(APP_ID):
			raise RuntimeError(tr("Приложение уже запущено или недоступен сеансовый D-Bus"))
		if not self.bus.registerObject("/Bridge", self, QDBusConnection.ExportAllSlots):
			raise RuntimeError(self.bus.lastError().message())
		self.reload()

	def reload(self):
		if not self.scripting.isValid():
			raise RuntimeError(tr("KWin недоступен. Запустите приложение внутри KDE Plasma 6."))
		self.scripting.call("unloadScript", APP_ID)
		if self.directory:
			self.directory.cleanup()
		self.directory = tempfile.TemporaryDirectory(prefix="why-here-")
		path = Path(self.directory.name) / "bridge.js"
		path.write_text(Path(__file__).with_name("kwin.js").read_text().replace("__TOKEN__", self.token))
		reply = self.scripting.call("loadScript", str(path), APP_ID)
		if reply.type() == QDBusMessage.ErrorMessage or not reply.arguments() or int(reply.arguments()[0]) < 0:
			raise RuntimeError(tr("Не удалось загрузить скрипт KWin: ") + reply.errorMessage())
		number = int(reply.arguments()[0])
		script = QDBusInterface("org.kde.KWin", f"/Scripting/Script{number}", "org.kde.kwin.Script", self.bus)
		reply = script.call("run")
		if reply.type() == QDBusMessage.ErrorMessage:
			raise RuntimeError(reply.errorMessage())

	def stop(self):
		if self.scripting.isValid():
			self.scripting.call("unloadScript", APP_ID)
		self.bus.unregisterObject("/Bridge")
		self.bus.unregisterService(APP_ID)
		if self.directory:
			self.directory.cleanup()
