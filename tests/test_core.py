import unittest
from why_here.core import APP_ID, Engine, identity


def window(wid, app="alpha"):
	return {"id": wid, "desktop": app, "normal": True}


class SessionsTest(unittest.TestCase):
	def setUp(self):
		self.time = 100
		self.engine = Engine(lambda: self.time)
		self.engine.configure(["desktop:alpha", "desktop:beta"])

	def test_shared_and_independent(self):
		e = self.engine
		self.assertEqual(e.sync([window("1")]), ["desktop:alpha"])
		e.start("desktop:alpha", "Цель", 3)
		deadline = e.sessions["desktop:alpha"].deadline
		e.sync([window("1"), window("2"), window("3", "beta")])
		e.start("desktop:beta", "Другая цель", 5)
		self.assertEqual(e.sessions["desktop:alpha"].windows, {"1", "2"})
		e.sync([window("2"), window("1"), window("3", "beta")])
		self.assertEqual(e.sessions["desktop:alpha"].deadline, deadline)
		self.assertNotEqual(e.sessions["desktop:beta"].deadline, deadline)
		e.sync([window("2")])
		self.assertIn("desktop:alpha", e.sessions)
		e.sync([])
		self.assertFalse(e.sessions)
		e.sync([window("4")])
		self.assertIsNone(e.sessions["desktop:alpha"].deadline)

	def test_warning_once_and_close_once(self):
		e = self.engine
		e.sync([window("1"), window("2"), window("3", "beta")])
		e.start("desktop:alpha", "Короткая цель", 1)
		self.assertEqual(e.tick(), (["desktop:alpha"], []))
		self.assertEqual(e.tick(), ([], []))
		self.time += 61
		self.assertEqual(e.tick()[1], [{"id": "1", "app": "desktop:alpha"}, {"id": "2", "app": "desktop:alpha"}])
		self.assertEqual(e.tick(), ([], []))
		self.assertIsNone(e.sessions["desktop:beta"].deadline)
		e.sync([window("1"), window("2"), window("4")])
		self.assertEqual(e.tick()[1], [{"id": "4", "app": "desktop:alpha"}])

	def test_disable_pending_and_self_exclusion(self):
		e = self.engine
		e.configure(["desktop:alpha", "desktop:" + APP_ID])
		e.sync([window("1"), window("self", APP_ID)])
		self.time += 10000
		self.assertEqual(e.tick(), ([], []))
		self.assertEqual(list(e.sessions), ["desktop:alpha"])
		e.start("desktop:alpha", "Цель", 1)
		e.configure([], False)
		self.assertFalse(e.sessions)
		self.assertEqual(e.tick(), ([], []))
		self.assertEqual(identity({"resource": "firefox"}), "class:firefox")
		self.assertEqual(identity({"desktop": "org.example.App"}), "desktop:org.example.App")
		self.assertEqual(identity({"resource": APP_ID}), "")

	def test_finish_now_and_session_mode(self):
		e = self.engine
		e.sync([window("1"), window("2", "beta")])
		e.start("desktop:alpha", "Цель", 15, "kill")
		e.start("desktop:beta", "Другая цель", 15)
		e.finish("desktop:alpha")
		self.assertEqual(e.tick()[1], [{"id": "1", "app": "desktop:alpha"}])
		self.assertTrue(e.sessions["desktop:alpha"].ended_manually)
		self.assertEqual(e.sessions["desktop:alpha"].end_mode, "kill")
		self.assertFalse(e.sessions["desktop:beta"].expired)
		e.finish("desktop:alpha")
		self.assertEqual(e.tick(), ([], []))

	def test_dismiss_pending(self):
		e = self.engine
		e.sync([window("1"), window("2", "beta")])
		e.dismiss_pending("desktop:alpha", "windows")
		self.assertIsNone(e.sessions["desktop:alpha"].deadline)
		e.dismiss_pending("desktop:alpha", "kill")
		self.assertEqual(e.tick(), ([], [{"id": "1", "app": "desktop:alpha"}]))
		self.assertEqual(e.sessions["desktop:alpha"].end_mode, "kill")
		self.assertEqual(e.sessions["desktop:alpha"].goal, "")
		self.assertIsNone(e.sessions["desktop:beta"].deadline)
		e.dismiss_pending("desktop:alpha", "kill")
		self.assertEqual(e.tick(), ([], []))
		e.configure([], False)
		e.dismiss_pending("desktop:beta", "kill")
		self.assertEqual(e.tick(), ([], []))

	def test_remove_tracking_and_validation(self):
		e = self.engine
		e.sync([window("1"), window("2", "beta")])
		with self.assertRaises(ValueError):
			e.start("desktop:alpha", "  ", 10)
		e.configure(["desktop:beta"])
		self.assertEqual(list(e.sessions), ["desktop:beta"])


if __name__ == "__main__":
	unittest.main()
