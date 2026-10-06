import ast
from pathlib import Path
import unittest

from why_here.i18n import EN, set_language, tr


class TranslationTest(unittest.TestCase):
	def tearDown(self):
		set_language("ru")

	def test_catalogue_covers_ui_messages(self):
		for path in Path("why_here").glob("*.py"):
			for node in ast.walk(ast.parse(path.read_text())):
				if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
					self.assertIsInstance(node.args[0], ast.Constant)
					self.assertIn(node.args[0].value, EN, f"Missing translation in {path}")

	def test_languages_and_interpolation(self):
		set_language("en")
		self.assertEqual(tr("Зачем я здесь?"), "Why am I here?")
		self.assertEqual(tr("Демо-программа {number}").format(number=2), "Demo application 2")
		self.assertEqual(tr("Отправлен SIGKILL"), "SIGKILL sent")
		set_language("ru")
		self.assertEqual(tr("Зачем я здесь?"), "Зачем я здесь?")
