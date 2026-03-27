# TranslationBuilder

TranslationBuilder is a QGIS plugin that scans a plugin’s source code and UI files to extract all translatable strings and generate `.ts` and `.qm` files **without using `lupdate`**.  
It provides a simple, cross‑platform workflow for managing translations in QGIS plugin development.

---

## ✨ Features

- Extracts translatable strings from:
  - Python files (`QCoreApplication.translate`)
  - Qt Designer `.ui` files
- Generates `.ts` translation files for any language
- Compiles `.qm` files using `lrelease`
- Works **without** requiring `lupdate`
- Automatic detection of `lrelease` on:
  - Windows  
  - macOS  
  - Linux  
- Manual selection of `lrelease` when needed
- Integrated button to launch **Qt Linguist**
- Preview of extracted strings
- Log panel for all operations
- Multi‑language support (e.g., `it`, `en`, `es`, `fr`)
- Compatible with **QGIS 4.x** and **Qt6**

---

## 🖥️ Requirements

- QGIS 4.0 or later  
- Qt6 (supported by QGIS 4)  
- `lrelease` available in your system or QGIS installation  
- Optional: Qt Linguist for editing translations

---

## 📦 Installation

1. Download the plugin or clone the repository.
2. Copy the folder into your QGIS plugins directory:
   - **Windows:** `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins`
   - **Linux:** `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins`
3. Restart QGIS.
4. Enable *TranslationBuilder* from:

---

## 🚀 Usage

1. Open the plugin from the QGIS toolbar or plugin menu.
2. Select:
- Plugin folder  
- i18n folder  
- Languages (comma‑separated)
3. Click **Generate TS** to create translation files.
4. Edit translations using **Qt Linguist** (button included).
5. Click **Generate QM** to compile `.qm` files.

---

## 🔧 Installing Qt Tools (linguist, lrelease, lupdate) via aqtinstall
TranslationBuilder requires the Qt translation tools (lrelease, lupdate, and optionally linguist).
These tools are normally included in full Qt installations, but you can install only the necessary components using aqtinstall, a lightweight Python-based installer.

1. Install aqtinstall

pip install aqtinstall

2. Install Qt 6.6.0 Tools (cross‑platform)
Use the command appropriate for your operating system.

* **Windows (MinGW 64‑bit)**: aqt install-qt windows desktop 6.6.0 win64_mingw -m qttools
* **macOS (Clang)**: aqt install-qt mac desktop 6.6.0 clang_64 -m qttools
* **Linux (GCC)**: aqt install-qt linux desktop 6.6.0 gcc_64 -m qttools

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPL‑3.0)**.  
See the `LICENSE` file for details.

---

## 👤 Author

**Faustino Cetraro**  
Scientific communicator, GIS specialist, and editorial architect.

---

## 🤝 Contributions

Contributions, suggestions, and improvements are welcome.  
Feel free to open issues or pull requests.
