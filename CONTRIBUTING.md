# Contributing / Участие

Please describe the issue or proposed change in Russian or English. For window
detection bugs, include the Plasma version, Wayland/X11 session type, installation
method (native or Flatpak), and the app ID displayed in Settings. Do not include
private goals or document titles.

Описывать ошибки и предложения можно на русском или английском. Для ошибок
обнаружения окон укажите версию Plasma, тип сеанса, способ установки программы
и её ID из настроек. Не публикуйте личные цели и названия документов.

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m why_here --demo
```

Use tabs in Python/JavaScript; configuration formats follow `.editorconfig`.
Add UI strings through `tr()` and update `why_here/i18n.py`. Never translate
user-entered goals or use window titles to determine process ownership.

```bash
.venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.gui_smoke
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.startup_smoke
QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.english_smoke
```

Changes to window or process handling also need the real KDE tests described in
[TESTING.md](TESTING.md). Use disposable test applications. Do not test termination
against apps containing unsaved work. Never substitute process-name matching or
process-group killing for the existing PID ownership checks.

A pull request should explain the user-visible change, tests performed, and any
remaining limitations. Keep unrelated changes separate.
