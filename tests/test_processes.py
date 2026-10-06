import os
import signal
import subprocess
import sys
import unittest

from why_here.processes import Processes


class ProcessTest(unittest.TestCase):
	def test_kill_target_tree_only(self):
		code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"
		target = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
		control = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
		child = int(target.stdout.readline())
		child_fd = os.pidfd_open(child)
		manager = Processes()
		try:
			windows = {"one": {"id": "one", "desktop": "test", "pid": target.pid}, "two": {"id": "two", "desktop": "other", "pid": control.pid}}
			manager.sync(list(windows.values()))
			self.assertEqual(manager.kill("desktop:test", {"one"}, windows), "Отправлен SIGKILL")
			self.assertEqual(target.wait(timeout=5), -signal.SIGKILL)
			import select
			self.assertTrue(select.select([child_fd], [], [], 5)[0], "Child still running")
			self.assertIsNone(control.poll())
		finally:
			manager.close()
			for process in (target, control):
				if process.poll() is None:
					process.kill()
				process.wait()
			target.stdout.close()
			os.close(child_fd)

	def test_shared_process_and_self_are_excluded(self):
		target = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
		manager = Processes()
		try:
			windows = {
				"one": {"id": "one", "desktop": "test", "pid": target.pid},
				"two": {"id": "two", "desktop": "other", "pid": target.pid},
				"self": {"id": "self", "desktop": "unknown", "pid": os.getpid()},
			}
			manager.sync(list(windows.values()))
			self.assertNotIn("self", manager.owners)
			self.assertIn("Отказ", manager.kill("desktop:test", {"one"}, windows))
			self.assertIsNone(target.poll())
			manager.sync([])
			self.assertFalse(manager.owners)
		finally:
			manager.close()
			target.kill()
			target.wait()
