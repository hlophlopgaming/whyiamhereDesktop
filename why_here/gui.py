from .i18n import tr, set_language
import math
import struct
import tempfile
import wave
from pathlib import Path
from importlib.metadata import version

from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QIcon, QPainter, QColor, QPalette
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
	QApplication, QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox, QFormLayout,
	QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
	QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSpinBox, QGraphicsOpacityEffect,
	QSystemTrayIcon, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .core import APP_ID, Engine, clock, identity
from .processes import Processes
from .storage import DEFAULTS, AUTOSTART, installed_apps, read_settings, remember_goal, save_settings, set_autostart


def button(text, function, layout):
	widget = QPushButton(text)
	widget.clicked.connect(function)
	layout.addWidget(widget)
	return widget


def duration(seconds):
	return f"{seconds // 60:02d}:{seconds % 60:02d}"


class GoalDialog(QDialog):
	def __init__(self, controller, key):
		super().__init__()
		self.controller, self.key = controller, key
		self.setWindowFlag(Qt.WindowStaysOnTopHint)
		self.setWindowModality(Qt.ApplicationModal)
		self.setWindowTitle(tr("Зачем я здесь? — ") + controller.name(key))
		self.setMinimumWidth(430)
		layout = QFormLayout(self)
		self.goal = QLineEdit()
		self.goal.setMaxLength(500)
		self.goal.setPlaceholderText(tr("Например: ответить на письмо"))
		self.goal.setCompleter(QCompleter(controller.goals(key), self.goal))
		self.goal.completer().setCaseSensitivity(Qt.CaseInsensitive)
		self.goal.completer().setFilterMode(Qt.MatchContains)
		self.minutes = QSpinBox()
		self.minutes.setRange(1, 1440)
		self.minutes.setValue(controller.settings["minutes"])
		self.minutes.setSuffix(tr(" мин"))
		layout.addRow(tr("Что тебе нужно в этой программе?"), self.goal)
		layout.addRow(tr("За сколько времени ты хочешь\nрешить свою проблему?"), self.minutes)
		quick = QHBoxLayout()
		for minutes in (5, 15, 30):
			button(tr("{minutes} мин").format(minutes=minutes), lambda checked=False, value=minutes: self.minutes.setValue(value), quick)
		layout.addRow(tr("Быстрый выбор"), quick)
		blocked = QLabel(tr("До начала сеанса окна программы заблокированы, а эту форму нельзя скрыть."))
		blocked.setWordWrap(True)
		layout.addRow(blocked)
		note = QLabel(tr("В режиме принудительного завершения закрытие этой формы\nкрестиком или Escape завершит программу без сохранения."))
		note.setWordWrap(True)
		layout.addRow(note)
		buttons = QDialogButtonBox()
		start = buttons.addButton(tr("Начать"), QDialogButtonBox.AcceptRole)
		start.setEnabled(False)
		self.goal.textChanged.connect(lambda value: start.setEnabled(bool(value.strip())))
		buttons.accepted.connect(lambda: controller.start_session(key, self.goal.text(), self.minutes.value()))
		self.rejected.connect(lambda: controller.dismiss_form(key))
		layout.addRow(buttons)

	def reject(self):
		if self.controller.stopping or self.controller.settings["end_mode"] == "kill":
			super().reject()
		else:
			QTimer.singleShot(0, self.restore_focus)

	def closeEvent(self, event):
		if self.controller.stopping or self.controller.settings["end_mode"] == "kill":
			super().closeEvent(event)
		else:
			event.ignore()
			QTimer.singleShot(0, self.restore_focus)

	def restore_focus(self):
		self.show()
		self.raise_()
		self.activateWindow()


class Reminder(QWidget):
	def __init__(self, finish):
		super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
		self.setAttribute(Qt.WA_ShowWithoutActivating)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self.effective_opacity = 0.8
		self.warning = False
		self.setWindowTitle(tr("Зачем я здесь? — напоминание"))
		self.setFixedWidth(340)
		layout = QVBoxLayout(self)
		self.label = QLabel()
		self.label.setTextFormat(Qt.PlainText)
		self.label.setWordWrap(True)
		self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
		layout.addWidget(self.label)
		self.text_opacity = QGraphicsOpacityEffect(self.label)
		self.label.setGraphicsEffect(self.text_opacity)
		self.finish_button = button(tr("Завершить сейчас"), finish, layout)
		self.finish_button.setFocusPolicy(Qt.NoFocus)
		self.setToolTip(tr("Перетащите напоминание за текст или фон"))

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)
		color = QColor("#b32632") if self.warning else self.palette().color(QPalette.Window)
		color.setAlphaF(self.effective_opacity)
		painter.setBrush(color)
		painter.setPen(Qt.NoPen)
		painter.drawRoundedRect(self.rect(), 10, 10)

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton and self.windowHandle():
			self.windowHandle().startSystemMove()

	def update_session(self, name, session, opacity):
		text = session.end_status or (tr("Сеанс завершён") if session.ended_manually else tr("Время вышло")) if session.expired else duration(session.remaining(clock()))
		self.finish_button.setEnabled(not session.expired)
		mode = tr("Принудительное завершение программы") if session.end_mode == "kill" else tr("Закрытие окон")
		self.label.setText(f"{name}\n{session.goal}\n{text}\n{mode}")
		self.warning = session.warned
		self.effective_opacity = 1.0 if session.warned else opacity / 100
		self.label.setStyleSheet("padding: 8px; color: white;" if session.warned else "padding: 8px;")
		self.text_opacity.setOpacity(self.effective_opacity)
		self.update()
		self.adjustSize()


class SettingsWindow(QMainWindow):
	def __init__(self, controller):
		super().__init__()
		self.controller = controller
		self.setWindowTitle(tr("Зачем я здесь?"))
		self.resize(800, 650)
		body = QWidget()
		self.setCentralWidget(body)
		layout = QVBoxLayout(body)
		title = QLabel(tr("Зачем я здесь?"))
		font = title.font()
		font.setPointSize(22)
		title.setFont(font)
		brand = QHBoxLayout()
		logo = QLabel()
		logo.setPixmap(QIcon(str(Path(__file__).with_name("assets") / "icon.png")).pixmap(48, 48))
		brand.addWidget(logo)
		brand.addWidget(title, 1)
		layout.addLayout(brand)
		layout.addWidget(QLabel(tr("Открой программу. Назови цель. Выдели время.")))
		self.status = QLabel(tr("Демонстрация: реальные окна не закрываются") if controller.demo else tr("Подключение к KWin…"))
		self.status.setWordWrap(True)
		layout.addWidget(self.status)
		self.enabled = QCheckBox(tr("Отслеживание включено"))
		self.enabled.setChecked(controller.settings["enabled"])
		self.enabled.toggled.connect(controller.set_enabled)
		layout.addWidget(self.enabled)
		layout.addWidget(QLabel(tr("Отслеживаемые программы")))
		self.apps = QListWidget()
		layout.addWidget(self.apps)
		row = QHBoxLayout()
		layout.addLayout(row)
		button(tr("Из открытых окон…"), lambda: self.pick(True), row)
		button(tr("Из установленных…"), lambda: self.pick(False), row)
		button(tr("Удалить"), self.remove_app, row)
		form = QFormLayout()
		layout.addLayout(form)
		self.minutes = QSpinBox()
		self.minutes.setRange(1, 1440)
		self.minutes.setValue(controller.settings["minutes"])
		self.warning = QSpinBox()
		self.warning.setRange(0, 1440)
		self.warning.setValue(controller.settings["warning"])
		self.opacity = QSlider(Qt.Horizontal)
		self.opacity.setRange(25, 100)
		self.opacity.setValue(controller.settings["opacity"])
		self.sound = QCheckBox(tr("Звуковой сигнал при предупреждении"))
		self.sound.setChecked(controller.settings["sound"])
		self.autostart = QCheckBox(tr("Запускать при входе в KDE"))
		self.autostart.setChecked(AUTOSTART.exists())
		self.autostart.setEnabled(not controller.demo)
		form.addRow(tr("Время по умолчанию, мин"), self.minutes)
		form.addRow(tr("Предупреждать за, мин (0 — в конце)"), self.warning)
		form.addRow(tr("Непрозрачность напоминания"), self.opacity)
		form.addRow(self.sound)
		self.end_mode = QComboBox()
		self.end_mode.addItem(tr("Закрыть окна"), "windows")
		self.end_mode.addItem(tr("Принудительно завершить программу (SIGKILL)"), "kill")
		self.end_mode.setCurrentIndex(max(0, self.end_mode.findData(controller.settings["end_mode"])))
		form.addRow(tr("По окончании новых сессий"), self.end_mode)
		note = QLabel(tr("Завершение процесса может привести к потере несохранённых данных.\nКнопка на напоминании применяет режим сессии досрочно."))
		note.setWordWrap(True)
		form.addRow(note)
		self.end_mode.currentIndexChanged.connect(self.save_options)
		form.addRow(self.autostart)
		self.language = QComboBox()
		self.language.addItem("Русский", "ru")
		self.language.addItem("English", "en")
		self.language.setCurrentIndex(self.language.findData(controller.settings["language"]))
		form.addRow(tr("Язык / Language (после перезапуска)"), self.language)
		self.language.currentIndexChanged.connect(self.save_options)
		for widget in (self.minutes, self.warning, self.opacity):
			widget.valueChanged.connect(self.save_options)
		self.sound.toggled.connect(self.save_options)
		self.autostart.toggled.connect(self.change_autostart)
		layout.addWidget(QLabel(tr("Текущие сессии · двойной щелчок открывает ожидающую форму")))
		self.sessions = QTableWidget(0, 3)
		self.sessions.setHorizontalHeaderLabels([tr("Программа"), tr("Цель"), tr("Осталось")])
		self.sessions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
		self.sessions.setEditTriggers(QTableWidget.NoEditTriggers)
		self.sessions.cellDoubleClicked.connect(self.open_pending)
		layout.addWidget(self.sessions)
		row = QHBoxLayout()
		layout.addLayout(row)
		button(tr("Ожидающие формы"), controller.show_pending, row)
		if controller.demo:
			button(tr("Новая демо-сессия"), controller.new_demo, row)
			button(tr("Предупреждение"), lambda: controller.advance_demo(False), row)
			button(tr("Завершить"), lambda: controller.advance_demo(True), row)
		else:
			button(tr("Переподключить KWin"), controller.reconnect, row)
		button(tr("Выйти"), controller.app.quit, row)
		self.version_label = QLabel(f"v{version('why-am-i-here-kde')}")
		font = self.version_label.font()
		font.setPointSizeF(max(6, font.pointSizeF() - 2))
		self.version_label.setFont(font)
		layout.addWidget(self.version_label, alignment=Qt.AlignLeft)
		self.refresh_apps()

	def refresh_apps(self):
		self.apps.clear()
		for key, name in self.controller.settings["apps"].items():
			item = QListWidgetItem(f"{name} — {key}")
			item.setData(Qt.UserRole, key)
			self.apps.addItem(item)

	def pick(self, opened):
		choices = {identity(w): f'{w["caption"]} — {identity(w)}' for w in self.controller.engine.windows.values()} if opened else installed_apps()
		dialog = QDialog(self)
		dialog.setWindowTitle(tr("Выберите программу") + (tr(" по данным KWin") if opened else tr(" из меню приложений")))
		dialog.resize(650, 450)
		layout = QVBoxLayout(dialog)
		note = QLabel(tr("Выбор открытого окна надёжнее: используется фактический идентификатор KWin.\nЕсли выбранная из меню программа не определяется, добавьте её из открытых окон."))
		note.setWordWrap(True)
		layout.addWidget(note)
		search = QLineEdit()
		search.setPlaceholderText(tr("Поиск…"))
		layout.addWidget(search)
		items = QListWidget()
		layout.addWidget(items)
		for key, name in sorted(choices.items(), key=lambda pair: pair[1].casefold()):
			if not key:
				continue
			item = QListWidgetItem(f"{name} · {key}")
			item.setData(Qt.UserRole, key)
			items.addItem(item)
		search.textChanged.connect(lambda text: [items.item(i).setHidden(text.casefold() not in items.item(i).text().casefold()) for i in range(items.count())])
		def accept():
			item = items.currentItem()
			if item:
				key = item.data(Qt.UserRole)
				self.controller.settings["apps"][key] = installed_apps().get(key, key.split(":", 1)[-1]) if opened else choices[key]
				self.controller.configure()
				self.refresh_apps()
				dialog.accept()
		button(tr("Отслеживать"), accept, layout)
		items.itemDoubleClicked.connect(lambda item: accept())
		dialog.exec()

	def remove_app(self):
		item = self.apps.currentItem()
		if item:
			self.controller.settings["apps"].pop(item.data(Qt.UserRole), None)
			self.controller.configure()
			self.refresh_apps()

	def save_options(self):
		self.controller.settings.update(minutes=self.minutes.value(), warning=self.warning.value(), opacity=self.opacity.value(), sound=self.sound.isChecked(), end_mode=self.end_mode.currentData(), language=self.language.currentData())
		self.controller.configure()

	def change_autostart(self, enabled):
		try:
			set_autostart(enabled)
		except OSError as error:
			QMessageBox.warning(self, tr("Автозапуск"), str(error))
			self.autostart.blockSignals(True)
			self.autostart.setChecked(AUTOSTART.exists())
			self.autostart.blockSignals(False)

	def open_pending(self, row, column):
		item = self.sessions.item(row, 0)
		if item:
			self.controller.show_form(item.data(Qt.UserRole))

	def closeEvent(self, event):
		if QSystemTrayIcon.isSystemTrayAvailable():
			event.ignore()
			self.hide()
		else:
			self.controller.app.quit()


class Controller(QObject):
	def __init__(self, app, demo=False, language=None):
		super().__init__()
		self.app, self.demo = app, demo
		self.stopping = False
		self.settings, error = (DEFAULTS | {"apps": {}, "goals": {}}, "") if demo else read_settings()
		self.settings["language"] = language or self.settings["language"]
		set_language(self.settings["language"])
		self.engine = Engine()
		self.processes = Processes()
		self.forms, self.reminders = {}, {}
		self.bridge = None
		self.demo_number = 0
		self.demo_closes = 0
		self.sound_dir = tempfile.TemporaryDirectory(prefix="why-here-sound-")
		path = Path(self.sound_dir.name) / "warning.wav"
		with wave.open(str(path), "wb") as sound:
			sound.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
			sound.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 660 * i / 22050) * min(1, i / 220, (6600 - i) / 220))) for i in range(6600)))
		self.sound = None if demo else QSoundEffect(self)
		if self.sound:
			self.sound.setSource(QUrl.fromLocalFile(str(path)))
			self.sound.setVolume(0.5)
		self.window = SettingsWindow(self)
		icon = QIcon(str(Path(__file__).with_name("assets") / "icon.png"))
		app.setWindowIcon(icon)
		self.tray = QSystemTrayIcon(icon, self)
		self.tray.setToolTip(tr("Зачем я здесь?"))
		self.menu = QMenu()
		self.menu.addAction(tr("Открыть настройки"), self.show_settings)
		self.menu.addAction(tr("Ожидающие формы"), self.show_pending)
		self.toggle = QAction(tr("Отслеживание включено"), self.menu)
		self.toggle.setCheckable(True)
		self.toggle.setChecked(self.settings["enabled"])
		self.toggle.toggled.connect(self.set_enabled)
		self.menu.addAction(self.toggle)
		self.menu.addSeparator()
		self.menu.addAction(tr("Выйти"), app.quit)
		self.tray.setContextMenu(self.menu)
		self.tray.activated.connect(lambda reason: self.show_settings() if reason == QSystemTrayIcon.Trigger else None)
		self.tray.show()
		self.configure(save=False)
		self.timer = QTimer(self)
		self.timer.setInterval(250)
		self.timer.timeout.connect(self.tick)
		self.timer.start()
		if error:
			QTimer.singleShot(0, lambda: QMessageBox.warning(self.window, tr("Настройки"), error))
		app.aboutToQuit.connect(self.cleanup)

	def name(self, key):
		return self.settings["apps"].get(key, key.removeprefix("desktop:").removeprefix("class:"))

	def goals(self, key):
		return self.settings["goals"].get(key, [])

	def remember_goal(self, key, goal):
		remember_goal(self.settings, key, goal)
		if not self.demo:
			try:
				save_settings(self.settings)
			except OSError as error:
				QMessageBox.warning(self.window, tr("Не удалось сохранить настройки"), str(error))

	def configure(self, save=True):
		added = self.engine.configure(self.settings["apps"], self.settings["enabled"], self.settings["warning"] * 60)
		if save and not self.demo:
			try:
				save_settings(self.settings)
			except OSError as error:
				QMessageBox.warning(self.window, tr("Не удалось сохранить настройки"), str(error))
		self.reconcile(added)

	def set_enabled(self, enabled):
		self.settings["enabled"] = enabled
		for widget in (self.window.enabled, self.toggle):
			widget.blockSignals(True)
			widget.setChecked(enabled)
			widget.blockSignals(False)
		self.configure()

	def reconcile(self, added):
		for collection in (self.forms, self.reminders):
			for key in list(collection):
				if key not in self.engine.sessions:
					collection.pop(key).deleteLater()
		for key in added:
			QTimer.singleShot(0, lambda key=key: self.show_form(key, automatic=True))

	def snapshot(self, windows):
		self.processes.sync(windows)
		self.reconcile(self.engine.sync(windows))
		warnings, commands = self.engine.tick()
		self.warn(warnings)
		close = []
		killed = set()
		for command in commands:
			key = command["app"]
			session = self.engine.sessions[key]
			if session.end_mode == "kill":
				if key not in killed:
					session.end_status = self.processes.kill(key, session.windows, self.engine.windows)
					killed.add(key)
			else:
				session.end_status = tr("Запрос закрытия отправлен")
				close.append(command)
		return [*self.engine.blocks(), *close]

	def warn(self, warnings):
		for key in warnings:
			if self.settings["sound"] and self.sound:
				self.sound.play()

	def show_settings(self):
		self.window.show()
		self.window.raise_()
		self.window.activateWindow()

	def show_form(self, key, automatic=False):
		session = self.engine.sessions.get(key)
		if session is None or session.deadline is not None:
			return
		if key not in self.forms:
			self.forms[key] = GoalDialog(self, key)
		form = self.forms[key]
		form.show()
		form.raise_()
		form.activateWindow()
		QApplication.alert(form)

	def show_pending(self):
		for key in self.engine.sessions:
			self.show_form(key)

	def dismiss_form(self, key):
		if self.stopping:
			return
		self.engine.dismiss_pending(key, self.settings["end_mode"])
		self.tick()

	def start_session(self, key, goal, minutes):
		if key not in self.engine.sessions:
			return
		self.engine.start(key, goal, minutes, self.settings["end_mode"])
		self.remember_goal(key, goal)
		self.forms[key].hide()
		reminder = Reminder(lambda: self.finish_session(key))
		self.reminders[key] = reminder
		reminder.update_session(self.name(key), self.engine.sessions[key], self.settings["opacity"])
		reminder.finish_button.setToolTip(tr("Принудительно завершить программу без сохранения") if self.settings["end_mode"] == "kill" else tr("Отправить запрос закрытия окон"))
		reminder.show()
		self.tick()

	def finish_session(self, key):
		self.engine.finish(key)
		self.tick()

	def tick(self):
		if self.demo:
			warnings, commands = self.engine.tick()
			self.warn(warnings)
			self.demo_closes += len(commands)
			if commands:
				self.window.status.setText(tr("Демонстрация: имитировано закрытий — {count}. Реальные окна не затронуты.").format(count=self.demo_closes))
		elif self.bridge:
			connected = clock() - self.bridge.last_seen < 3
			self.window.status.setText(tr("KWin подключён") if connected else tr("Нет связи с KWin. Закрытие недоступно. Нажмите «Переподключить KWin»."))
		self.window.sessions.setRowCount(len(self.engine.sessions))
		for row, (key, session) in enumerate(self.engine.sessions.items()):
			remaining = session.remaining(clock())
			state = tr("Ожидает ответа") if remaining is None else ((session.end_status or tr("Сеанс завершён")) if session.expired else duration(remaining))
			for column, text in enumerate((self.name(key), session.goal or "—", state)):
				item = QTableWidgetItem(text)
				item.setData(Qt.UserRole, key)
				self.window.sessions.setItem(row, column, item)
			if key in self.reminders:
				self.reminders[key].update_session(self.name(key), session, self.settings["opacity"])

	def new_demo(self):
		self.demo_number += 1
		key = f"desktop:demo{self.demo_number}"
		self.settings["apps"][key] = tr("Демо-программа {number}").format(number=self.demo_number)
		self.configure(save=False)
		windows = list(self.engine.windows.values()) + [{"id": key, "desktop": key[8:], "caption": tr("Демонстрация")}]
		self.reconcile(self.engine.sync(windows))
		self.window.refresh_apps()

	def advance_demo(self, end):
		for session in self.engine.sessions.values():
			if session.deadline is not None:
				session.deadline = clock() + (0 if end else max(1, self.engine.warning))
		self.tick()

	def reconnect(self):
		if self.bridge:
			try:
				self.bridge.reload()
			except RuntimeError as error:
				QMessageBox.warning(self.window, "KWin", str(error))

	def cleanup(self):
		self.stopping = True
		if self.bridge:
			self.bridge.stop()
		self.processes.close()
		self.tray.hide()
		if self.sound:
			self.sound.stop()
		self.sound_dir.cleanup()
