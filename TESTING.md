# Testing / Проверки

Run commands from the repository root after installing `requirements.txt`.
Команды выполняются из корня проекта после установки `requirements.txt`.

## Automated checks / Автоматические тесты

```bash
.venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.gui_smoke
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.startup_smoke
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.english_smoke
```

The unit suite covers session grouping, independent deadlines, last-window cleanup,
one-time warnings, manual ending, unanswered-form dismissal, tracking cancellation,
application IDs ending in `.desktop`, process-tree isolation, protected/shared
processes, goal history, generated autostart entries and translation catalogue
coverage.

GUI checks exercise forms, reminders, both languages, bundled icons, the tray's
actions, safe demo ending and startup without an automatic goal form. Offscreen
warnings about unsupported window raising or the tray are expected.

Юнит-тесты проверяют сессии, таймеры, закрытие формы, исключение собственных окон,
сопоставление ID, безопасность завершения процессов и переводы. GUI-тесты
проверяют оба языка, формы и напоминания. Headless-проверка не доказывает работу
композитора Wayland.

## Real KDE / Настоящий KDE

Inside a Plasma 6 session:

```bash
.venv/bin/python -m tests.gui_smoke
.venv/bin/python -m tests.english_smoke
.venv/bin/python -m tests.kwin_integration
.venv/bin/python -m tests.kwin_integration --kill
.venv/bin/python -m tests.kwin_integration --dismiss
```

Each KWin test creates two windows of a uniquely identified test app and one
control window. It uses its own D-Bus service and may run alongside the utility.
The default test sends ordinary close requests. `--kill` verifies SIGKILL of a
resident test app; `--dismiss` closes the actual unanswered goal form. The control
app must survive. The tests also verify that pending windows are minimized,
restored after answering and that KWin activates the goal form. Cleanup affects
only test-owned child processes.

Тесты KWin создают отдельные тестовые программы и используют собственный D-Bus
сервис. Пользовательские приложения не выбираются. Проверяются обычное закрытие,
SIGKILL и закрытие формы без ответа; контрольная программа должна остаться работать.

## Validation record / Результаты

On 2026-10-06, the following passed locally on EndeavourOS, KDE Plasma 6.7.4,
Wayland, Python 3.14 and PySide6 6.11.2:

- 14 unit tests and Russian/English GUI smoke checks.
- All three real KWin test modes.
- Python wheel and entry point creation, desktop-file validation and autostart
  file enable/disable.
- Standalone PyInstaller executable startup from outside the source directory,
  including English CLI help and the Wayland demo.

The GitHub workflow runs the unit and offscreen checks on Ubuntu 24.04 / Python
3.12. Its first remote execution will happen after the repository is published;
it has not been run on GitHub during local preparation.

14 тестов и реальные проверки KWin прошли локально. Workflow подготовлен,
но запуск на GitHub до публикации не выполнялся.

## Manual checks still needed / Ручная проверка

- Your specific Flatpak applications and any detached background services.
- Save-document dialogs in third-party editors, using disposable documents.
- Audible output on your chosen sound device.
- Long typing sessions with a visible reminder, dragging, multiple monitors,
  fullscreen apps, lock/unlock and autostart after a fresh KDE login.

Проверьте свои Flatpak-программы, сохранение тестовых документов, слышимость звука,
перетаскивание, блокировку и возврат фокуса, несколько мониторов и новый вход в KDE.
Не используйте несохранённые важные документы для проверки SIGKILL.
