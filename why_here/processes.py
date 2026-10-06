"""Terminate only pinned window-owner processes and their current descendants."""
from .i18n import tr
import os
import signal
from pathlib import Path

from .core import identity


def process_info(pid):
	path = Path(f"/proc/{pid}")
	if pid <= 1 or path.stat().st_uid != os.getuid():
		raise ValueError(tr("Процесс не принадлежит текущему пользователю"))
	fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
	return int(fields[1]), fields[19]


def protected_pids():
	protected = {1}
	pid = os.getpid()
	while pid > 1 and pid not in protected:
		protected.add(pid)
		try:
			pid = process_info(pid)[0]
		except (OSError, ValueError):
			break
	return protected


def pin(pid):
	if pid in protected_pids():
		raise ValueError(tr("Служебный процесс исключён"))
	fd = os.pidfd_open(pid)
	try:
		info = process_info(pid)
		executable = Path(f"/proc/{pid}/exe").resolve().name
		if executable in {"kwin_wayland", "kwin_x11", "plasmashell", "Xwayland", "dbus-daemon", "dbus-broker", "systemd"}:
			raise ValueError(tr("Служебный процесс исключён"))
		signal.pidfd_send_signal(fd, 0)
		return fd, info[1]
	except Exception:
		os.close(fd)
		raise


class Processes:
	def __init__(self):
		self.owners = {}

	def sync(self, windows):
		live = {w["id"]: w for w in windows if identity(w)}
		for wid in list(self.owners):
			pid, fd, birth = self.owners[wid]
			if wid not in live or live[wid].get("pid") != pid:
				os.close(fd)
				del self.owners[wid]
		for wid, window in live.items():
			pid = window.get("pid")
			if wid in self.owners or type(pid) is not int or pid <= 1:
				continue
			try:
				fd, birth = pin(pid)
				self.owners[wid] = pid, fd, birth
			except (OSError, ValueError):
				continue

	def kill(self, app, window_ids, windows):
		roots = {}
		for wid in window_ids:
			if wid in self.owners and wid in windows and identity(windows[wid]) == app:
				pid, fd, birth = self.owners[wid]
				try:
					signal.pidfd_send_signal(fd, 0)
					if process_info(pid)[1] == birth:
						roots[pid] = fd
				except (OSError, ValueError):
					continue
		if not roots:
			return tr("Не удалось определить процесс программы")
		# Never signal process groups or search for processes by executable name.
		table = {}
		for path in Path("/proc").iterdir():
			if path.name.isdigit():
				try:
					table[int(path.name)] = process_info(int(path.name))
				except (OSError, ValueError):
					continue
		targets = set(roots)
		while True:
			children = {pid for pid, (parent, birth) in table.items() if parent in targets}
			if children <= targets:
				break
			targets |= children
		foreign = {w.get("pid") for w in windows.values() if identity(w) != app}
		if targets & (foreign | protected_pids()):
			return tr("Отказ: процесс связан с другим приложением")
		fds = dict(roots)
		extra = []
		try:
			for pid in targets - roots.keys():
				try:
					fd, birth = pin(pid)
					extra.append(fd)
					if birth == table[pid][1]:
						fds[pid] = fd
				except (OSError, ValueError):
					continue
			failed = False
			# Kill children before parents; all handles are pinned against PID reuse.
			for pid in [*(targets - roots.keys()), *roots]:
				if pid not in fds:
					continue
				try:
					signal.pidfd_send_signal(fds[pid], signal.SIGKILL)
				except ProcessLookupError:
					pass
				except OSError:
					failed = True
			return tr("Не удалось завершить часть процессов") if failed else tr("Отправлен SIGKILL")
		finally:
			for fd in extra:
				os.close(fd)

	def close(self):
		for pid, fd, birth in self.owners.values():
			os.close(fd)
		self.owners.clear()
