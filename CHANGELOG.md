# Changelog  
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-03-27
### Added
- Initial public release of **TranslationBuilder**.
- Extraction of translatable strings from Python files using `QCoreApplication.translate`.
- Extraction of strings from `.ui` files via XML parsing.
- Generation of `.ts` files for multiple languages.
- Compilation of `.qm` files using `lrelease` (multi‑platform).
- Automatic detection of `lrelease` on Windows, macOS, and Linux.
- Manual selection of `lrelease` with persistent storage (QSettings + TXT file).
- Integrated button to launch **Qt Linguist** across all platforms.
- Preview panel for extracted strings.
- Log panel for all operations.
- Clean and responsive UI layout compatible with QGIS 4 and Qt6.
- Plugin metadata and GPL‑3 license.

### Fixed
- Correct handling of duplicate strings across Python and UI files.
- Improved path normalization for cross‑platform compatibility.

### Notes
- Requires QGIS 4.0 or later.
- Supports Qt6.
- Depends on `qpip==1.1.1`.

---

## [Unreleased]
### Planned
- Optional support for `.qrc` file scanning.
- Automatic detection of Qt Linguist paths on more Linux distributions.
- Integration with QGIS Processing for batch translation workflows.
