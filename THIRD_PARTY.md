# Third-party components

The MIT license in [LICENSE](LICENSE) covers this project's original Python and
JavaScript code, documentation, and SVG/PNG brand assets. It does not change the
licenses of dependencies or system components.

- **PySide6 / Qt** — used for the GUI, D-Bus and audio. Refer to the licenses shipped
  with the installed packages and the [Qt licensing documentation](https://www.qt.io/licensing/).
- **Python** — the interpreter is included in a PyInstaller build; its license is
  available in the Python distribution.
- **PyInstaller** — a build tool, licensed under GPL with a distribution exception
  for generated applications; see its [license](https://pyinstaller.org/en/stable/license.html).
- **KDE / KWin** — system components used through the scripting API; they are not
  included in this source repository.

Source distributions do not vendor these dependencies. A packaged executable
contains third-party runtime libraries, so it must not be described as an
MIT-only binary. Before publishing a binary release, include the required license
notices and comply with the licenses of the actual libraries collected by the
build. The release workflow publishes the generated archive together with this
notice; release maintainers remain responsible for checking the exact collected
libraries before publishing a tag.

The warning sound used by the application is synthesized by the application's
own code.
