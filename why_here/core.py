"""Session state; no Qt, disk writes or process management."""
from .i18n import tr
import math
import time
from dataclasses import dataclass, field

APP_ID = "org.local.WhyHere"


def clock():
	# Includes suspend on Linux and is immune to wall-clock adjustments.
	return time.clock_gettime(time.CLOCK_BOOTTIME)


def identity(window):
	desktop = str(window.get("desktop", ""))
	# KWin returns an extensionless ID OR an absolute desktop-file path.
	# In an ID such as org.telegram.desktop, the suffix is part of the name.
	if desktop.startswith("/"):
		desktop = desktop.rsplit("/", 1)[-1].removesuffix(".desktop")
	resource = str(window.get("resource", ""))
	if desktop == APP_ID or resource == APP_ID:
		return ""
	return "desktop:" + desktop if desktop else ("class:" + resource if resource else "")


@dataclass
class Session:
	app: str
	windows: set = field(default_factory=set)
	goal: str = ""
	deadline: float | None = None
	warned: bool = False
	expired: bool = False
	requested: set = field(default_factory=set)
	end_mode: str = "windows"
	ended_manually: bool = False
	end_status: str = ""

	def remaining(self, now):
		return max(0, math.ceil(self.deadline - now)) if self.deadline is not None else None


class Engine:
	def __init__(self, now=clock):
		self.now = now
		self.enabled = True
		self.tracked = set()
		self.sessions = {}
		self.windows = {}
		self.warning = 120

	def configure(self, tracked, enabled=True, warning=120):
		self.tracked = set(tracked)
		self.enabled = enabled
		self.warning = warning
		return self.sync(list(self.windows.values()))

	def sync(self, windows):
		self.windows = {w["id"]: w for w in windows if identity(w) and w.get("normal", True)}
		groups = {}
		if self.enabled:
			for wid, window in self.windows.items():
				app = identity(window)
				if app in self.tracked:
					groups.setdefault(app, set()).add(wid)
		for app in list(self.sessions):
			if app not in groups:
				del self.sessions[app]
		added = []
		for app, ids in groups.items():
			if app not in self.sessions:
				self.sessions[app] = Session(app)
				added.append(app)
			self.sessions[app].windows = ids
		return added

	def start(self, app, goal, minutes, end_mode="windows"):
		if not goal.strip() or not 0 < minutes <= 1440:
			raise ValueError(tr("Укажите цель и время от 1 до 1440 минут"))
		session = self.sessions[app]
		if session.deadline is not None:
			return
		if end_mode not in {"windows", "kill"}:
			raise ValueError(tr("Неизвестный режим завершения"))
		session.end_mode = end_mode
		session.goal = goal.strip()
		session.deadline = self.now() + minutes * 60

	def dismiss_pending(self, app, end_mode):
		session = self.sessions.get(app)
		if end_mode != "kill" or session is None or session.deadline is not None:
			return
		session.end_mode = "kill"
		session.ended_manually = True
		session.warned = True
		session.deadline = self.now()

	def finish(self, app):
		session = self.sessions.get(app)
		if session is None or session.deadline is None or session.expired:
			return
		session.ended_manually = True
		session.deadline = self.now()

	def tick(self):
		warnings, close = [], []
		for app, session in self.sessions.items():
			if session.deadline is None:
				continue
			remaining = session.remaining(self.now())
			if remaining <= self.warning and not session.warned:
				session.warned = True
				warnings.append(app)
			if remaining == 0:
				session.expired = True
				for wid in sorted(session.windows - session.requested):
					close.append({"id": wid, "app": app})
					session.requested.add(wid)
		return warnings, close
