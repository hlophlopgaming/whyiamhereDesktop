from .i18n import tr, set_language
from .storage import read_settings
import argparse
import sys

from PySide6.QtDBus import QDBusConnection, QDBusInterface
from PySide6.QtWidgets import QApplication, QMessageBox

from .core import APP_ID


def main():
	preparser = argparse.ArgumentParser(add_help=False)
	preparser.add_argument("--language", choices=("ru", "en"))
	preargs, _ = preparser.parse_known_args()
	set_language(preargs.language or read_settings()[0]["language"])
	parser = argparse.ArgumentParser(description=tr("Зачем я здесь? — цели и время для программ"))
	parser.add_argument("--demo", action="store_true", help=tr("безопасная демонстрация без KWin"))
	parser.add_argument("--background", action="store_true", help=tr("запуск в трее"))
	parser.add_argument("--show", action="store_true", help=tr("открыть настройки"))
	parser.add_argument("--language", choices=("ru", "en"), help="Interface language / Язык интерфейса")
	args = parser.parse_args()
	app = QApplication(sys.argv[:1])
	app.setApplicationName(APP_ID)
	app.setDesktopFileName(APP_ID)
	app.setQuitOnLastWindowClosed(False)
	if not args.demo:
		interface = QDBusInterface(APP_ID, "/Bridge", APP_ID, QDBusConnection.sessionBus())
		if interface.isValid():
			if not args.background:
				interface.call("Show")
			return 0
	from .gui import Controller
	controller = Controller(app, args.demo, args.language)
	if not args.demo:
		from .bridge import Bridge
		controller.bridge = Bridge(controller)
		try:
			controller.bridge.start()
		except RuntimeError as error:
			QMessageBox.warning(controller.window, tr("Подключение KWin"), str(error))
	if not args.background or args.demo or not controller.tray.isSystemTrayAvailable():
		controller.show_settings()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())
