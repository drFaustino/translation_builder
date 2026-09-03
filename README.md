# TranslationBuilder

TranslationBuilder is a QGIS plugin that scans a plugin's Python source code and Qt Designer UI files, extracts translatable strings, and generates .ts and .qm translation files without using lupdate.

It provides a simple, cross-platform workflow for managing translations during QGIS plugin development.

<img width="1032" height="792" alt="img7" src="https://github.com/user-attachments/assets/93a72c08-ca0a-428e-802f-e9ece9cf8339" />


## ✨ Features
Extracts translatable strings from:
Python files using QCoreApplication.translate(...)
tr(...)
self.tr(...)
_tr(...)
self._tr(...)
Qt Designer .ui files
Detects custom translation wrapper methods such as _tr().
Resolves the translation context from the enclosing Python class instead of using a generic "Default" context.
Falls back to the Python module/file name for module-level translation calls.
Tracks every file where a string occurs.
Generates a single TS message with multiple <location> entries when the same string occurs in different files.
Generates .ts files for any supported language.
Supports multiple languages, for example:
it, en
it, en, fr
it, en, fr, de, es
Optional automatic translation using Argos Translate.
Automatic translation works locally using installed Argos language models.
No translation API key is required.
No external translation service is required for the actual translation process.
TS files are always generated before automatic translation is attempted.
If Argos is unavailable or a model is missing, TS generation still succeeds.
Compiles .ts files into .qm files using lrelease.
Works without requiring lupdate.
Automatically detects lrelease on:
Windows
macOS
Linux
Allows manual selection of lrelease.
Integrated button to launch Qt Linguist.
Preview of extracted strings.
Detailed operation log.
Bottom progress bar and status indicator.
Background worker using QThread.
QGIS remains responsive during scanning, TS generation, model installation, translation and QM compilation.
Compatible with QGIS 4.x and Qt6.

## ⚡ Responsive and fail-safe workflow

TranslationBuilder performs heavy operations in a background worker.

The QGIS interface remains responsive while the plugin:

scans Python and UI files;
generates TS files;
installs Argos language models;
performs automatic translation;
compiles QM files.

The TS-generation process is deliberately independent from automatic translation.

The .ts files are created before automatic translation starts. Therefore:

Argos Translate is not installed → TS files are still created.
A required Argos model is missing → TS files are still created.
A language pair is unavailable → TS files are still created.
Automatic translation fails → TS files are still created.
Translation produces an error → affected messages remain unfinished.

This makes automatic translation an optional convenience rather than a requirement for the plugin.

## ⚙️ Requirements
Required
QGIS 4.0 or later
Qt6
Python 3.12 or the Python version supplied with the compatible QGIS installation
lrelease for compiling .ts files into .qm
Optional
Qt Linguist for reviewing and editing translations
Argos Translate for local automatic translation

Argos Translate is not required to generate TS files.

## 📦 Installation
Download the plugin or clone the repository.
Copy the translation_builder folder into your QGIS plugins directory.

Typical locations are:

Windows
%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins

macOS
~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins

Linux
~/.local/share/QGIS/QGIS4/profiles/default/python/plugins

Restart QGIS.
Open the QGIS Plugin Manager.
Enable TranslationBuilder.

## 🚀 Usage
Open TranslationBuilder from the QGIS toolbar or plugin menu.
Select the QGIS plugin folder.
Select or create the i18n folder.
Enter the languages separated by commas.

For example:
it, en, fr, de

The first language is the source language: it
All subsequent languages are target languages:en, fr, de

### Click Generate TS.

TranslationBuilder scans the Python and .ui files and creates the TS files first.

If Argos Translate is installed and the required language models are available, automatic translation is attempted afterwards.

Review and correct the translations using Qt Linguist.

Click Generate QM to compile the TS files into QM files.

## 🈯 Automatic translation with Argos Translate

TranslationBuilder optionally supports Argos Translate for local automatic translation.

Argos does not require an API key.

The translation is performed locally using language models installed on the computer.

Install Argos Translate

Open the Python/QGIS terminal and install:

python -m pip install argostranslate


## Alternatively:

pip install argostranslate

Make sure the package is installed in the Python environment used by QGIS.

After installation, restart QGIS and use the Check Argos button in TranslationBuilder.

## 🌍 Installing Argos language models

Installing the Python package alone is not enough.

Argos also needs the language models corresponding to the translations you want to perform.

For example, if the language field contains: it, en

you need an Argos model capable of translating: Italian → English

TranslationBuilder provides an Install Models function that can download and install the required Argos language models.

Internet access is therefore required only when downloading/updating models.

Once the models are installed, translation can be performed locally.

## 🔒 No API key required

Unlike cloud translation services, the Argos workflow does not require:

DeepL API;
Google Translate API;
LibreTranslate server;
translation API keys;
an external translation endpoint.

The actual translation is performed locally by Argos Translate.

## 🛡️ Automatic translation is optional

Argos Translate is deliberately not part of the critical TS-generation process.

For example, if Argos is unavailable:

Python/UI scan
      ↓
TS generation
      ↓
TS files available
      ↓
Argos translation
      ↓
optional


Therefore a failure in Argos cannot prevent TranslationBuilder from generating the TS files.

Messages that cannot be automatically translated remain marked as:

<translation type="unfinished"></translation>


They can then be translated manually using Qt Linguist.

## 🧩 Translation wrappers

TranslationBuilder detects common QGIS/Qt translation patterns, including custom wrappers.

For example:

self.tr("Open")

self._tr("Open")

_tr("Open")

QCoreApplication.translate(
    "MyDialog",
    "Open"
)


The scanner attempts to determine the appropriate translation context from the surrounding Python class.

For example:

class MyDialog(QDialog):

    def _tr(self, text):
        return QCoreApplication.translate(
            "MyDialog",
            text
        )

    def create_ui(self):
        label = self._tr("Open")


The resulting TS message uses:

MyDialog


as its translation context.

## 🌐 Multiple languages

The language field supports multiple languages.

Example:

it, en, fr, de, es

TranslationBuilder interprets this as:

Position	Role
it	Source
en	Target
fr	Target
de	Target
es	Target

The generated files will follow the plugin naming convention:

plugin_it.ts
plugin_en.ts
plugin_fr.ts
plugin_de.ts
plugin_es.ts

## 🛠️ Installing Qt translation tools

TranslationBuilder uses lrelease to compile .ts files into .qm files.

Qt Linguist can optionally be used to edit translations.

The Qt translation tools are normally included with a full Qt installation.

If necessary, they can also be installed using aqtinstall.

### Install aqtinstall

pip install aqtinstall

Windows
aqt install-qt windows desktop 6.6.0 win64_mingw -m qttools

macOS
aqt install-qt mac desktop 6.6.0 clang_64 -m qttools

Linux
aqt install-qt linux desktop 6.6.0 gcc_64 -m qttools


The installed Qt Tools package contains the translation utilities such as:

lrelease
lupdate
linguist

TranslationBuilder does not require lupdate.

## 📝 Recommended workflow

For best results:

1. Develop the QGIS plugin
          ↓
2. Wrap user-visible strings with tr() / self.tr() / _tr()
          ↓
3. Open TranslationBuilder
          ↓
4. Scan the plugin
          ↓
5. Generate TS files
          ↓
6. Optionally install/use Argos Translate
          ↓
7. Review translations with Qt Linguist
          ↓
8. Generate QM files
          ↓
9. Distribute the plugin


Machine translations should always be reviewed before publishing.


## 📄 License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

See the LICENSE file for details.

## 👤 Author

Faustino Cetraro

Scientific communicator, GIS specialist, and editorial architect.

## 🤝 Contributions

Contributions, suggestions and improvements are welcome.

Feel free to open issues or pull requests.
