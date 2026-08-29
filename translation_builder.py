import ast
import os
import re
import shutil
import subprocess
import sys
import tokenize
import traceback

# Parsing and writing of .ui / .ts XML (some of it untrusted, third-party
# plugin content) goes exclusively through xml_safe, a small in-house
# module built directly on xml.parsers.expat with DOCTYPE/DTD rejected
# outright. xml.etree.ElementTree (and defusedxml, which wraps it) are
# intentionally not used anywhere in this plugin -- see xml_safe.py for
# the rationale.
from . import xml_safe

from qgis.PyQt import uic
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QObject,
    QProcess,
    QSettings,
    QThread,
    QTranslator,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog,
    QFileDialog,
    QMessageBox,
)


# =========================================================
# CONSTANTS
# =========================================================

PLUGIN_DIR = os.path.dirname(__file__)

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        PLUGIN_DIR,
        "ui",
        "translation_builder_dialog.ui",
    )
)


# =========================================================
# XML HELPERS
# =========================================================

# =========================================================
# XML HELPERS
# =========================================================

def _safe_xml_from_file(path):
    """
    Safely read and parse a local XML file (.ui / .ts).

    See xml_safe.py: parsing goes through xml.parsers.expat directly,
    with any DOCTYPE/DTD rejected outright (which rules out XXE and
    entity-expansion attacks), instead of xml.etree.ElementTree.
    """

    return xml_safe.parse_file(path)


def _write_xml_tree(root_element, path):
    """
    Write an Element tree (xml_safe.Element) as UTF-8 XML.
    """

    xml_safe.write_file(root_element, path)


# =========================================================
# PLUGIN
# =========================================================

class TranslationBuilder:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.action = None
        self.dlg = None

        self.translator = None
        self.current_locale = ""

        self.menu = QCoreApplication.translate(
            "TranslationBuilderDialog",
            "&Translation Builder",
        )

        self._load_translation()

    # =====================================================
    # PLUGIN TRANSLATION
    # =====================================================

    def _load_translation(self):

        settings = QSettings()

        locale_value = settings.value(
            "locale/userLocale",
            "it",
        )

        locale_value = str(
            locale_value or "it"
        ).strip()

        candidates = []

        for locale in (
            locale_value,
            locale_value.replace("-", "_"),
            locale_value.split("_")[0],
        ):
            if locale and locale not in candidates:
                candidates.append(locale)

        i18n_dir = os.path.join(
            self.plugin_dir,
            "resources",
            "i18n",
        )

        for locale in candidates:

            qm_path = os.path.join(
                i18n_dir,
                f"translation_builder_{locale}.qm",
            )

            if not os.path.isfile(qm_path):
                continue

            translator = QTranslator()

            if translator.load(qm_path):

                QCoreApplication.installTranslator(
                    translator
                )

                self.translator = translator
                self.current_locale = locale

                break

    # =====================================================
    # GUI
    # =====================================================

    def initGui(self):

        icon_path = os.path.join(
            self.plugin_dir,
            "resources",
            "images",
            "icon.png",
        )

        self.action = QAction(
            QIcon(icon_path),
            QCoreApplication.translate(
                "TranslationBuilderDialog",
                "Translation Builder",
            ),
            self.iface.mainWindow(),
        )

        self.action.triggered.connect(
            self.run
        )

        self.iface.addPluginToMenu(
            self.menu,
            self.action,
        )

        self.iface.addToolBarIcon(
            self.action
        )

    # =====================================================
    # UNLOAD
    # =====================================================

    def unload(self):

        if self.action is not None:

            self.iface.removePluginMenu(
                self.menu,
                self.action,
            )

            self.iface.removeToolBarIcon(
                self.action
            )

            self.action = None

        if self.translator is not None:

            QCoreApplication.removeTranslator(
                self.translator
            )

            self.translator = None

    # =====================================================
    # RUN
    # =====================================================

    def run(self):

        if self.dlg is None:

            self.dlg = TranslationBuilderDialog(
                self.iface
            )

        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()


# =========================================================
# WORKER
# =========================================================

class TranslationBuilderWorker(QObject):

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    progress = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    preview_message = pyqtSignal(str)

    def __init__(self, task, args):
        super().__init__()

        self.task = task
        self.args = args

    def run(self):

        try:

            result = self.task(
                *self.args,
                log_callback=self.log_message.emit,
                progress_callback=self.progress.emit,
                preview_callback=self.preview_message.emit,
            )

            self.finished.emit(result)

        except Exception as error:

            self.failed.emit(
                f"{error}\n\n"
                f"{traceback.format_exc()}"
            )


# =========================================================
# DIALOG
# =========================================================

class TranslationBuilderDialog(
    QDialog,
    FORM_CLASS,
):

    # =====================================================
    # INIT
    # =====================================================

    def __init__(self, iface):

        super().__init__(
            iface.mainWindow()
        )

        self.iface = iface

        self.setupUi(self)

        self._thread = None
        self._worker = None
        self._busy = False

        self._last_py_files = []
        self._last_ui_files = []

        self._configure_ui()
        self._connect_signals()
        self._load_settings()

        self.check_argos()

    # =====================================================
    # UI
    # =====================================================

    def _configure_ui(self):

        if hasattr(self, "progressBar"):
            self.progressBar.setVisible(False)

        if hasattr(self, "txtArgosStatus"):

            self.txtArgosStatus.setReadOnly(True)

            self.txtArgosStatus.setStyleSheet(
                """
                QTextEdit {
                    background-color: #f5f5f5;
                    border: 1px solid #cccccc;
                    padding: 4px;
                }
                """
            )

        if hasattr(self, "labelGuide"):

            self.labelGuide.setTextFormat(
                Qt.TextFormat.RichText
            )

            self.labelGuide.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )

            self.labelGuide.setOpenExternalLinks(True)

    # =====================================================
    # SIGNALS
    # =====================================================

    def _connect_signals(self):

        connections = {
            "btnSelectPlugin": self.select_plugin_folder,
            "btnSelectI18n": self.select_i18n_folder,
            "btnSelectLrelease": self.select_lrelease,
            "btnGenerateTS": self.generate_ts,
            "btnGenerateQM": self.generate_qm,
            "btnOpenLinguist": self.open_linguist,
            "btnInstallArgos": self.install_argos_models,
            "btnCheckArgos": self.check_argos,
            "btnClear": self.clear_ui,
            "btnClose": self.close,
        }

        for name, callback in connections.items():

            if hasattr(self, name):

                getattr(self, name).clicked.connect(
                    callback
                )

    # =====================================================
    # SETTINGS
    # =====================================================

    def _load_settings(self):

        settings = QSettings()

        if hasattr(self, "txtLreleasePath"):

            self.txtLreleasePath.setText(
                str(
                    settings.value(
                        "translation_builder/lrelease_path",
                        "",
                    )
                    or ""
                )
            )

        languages = settings.value(
            "translation_builder/languages",
            "it, en",
        )

        if hasattr(self, "txtLanguages"):

            self.txtLanguages.setText(
                str(
                    languages or "it, en"
                )
            )

    # =====================================================
    # BUSY
    # =====================================================

    def _set_busy(self, busy):

        self._busy = bool(busy)

        button_names = (
            "btnGenerateTS",
            "btnGenerateQM",
            "btnOpenLinguist",
            "btnSelectPlugin",
            "btnSelectI18n",
            "btnSelectLrelease",
            "btnInstallArgos",
            "btnCheckArgos",
        )

        for name in button_names:

            if hasattr(self, name):

                getattr(self, name).setEnabled(
                    not busy
                )

        if hasattr(self, "btnClear"):

            self.btnClear.setEnabled(
                not busy
            )

        if hasattr(self, "progressBar"):

            self.progressBar.setVisible(busy)

            if busy:
                self.progressBar.setValue(0)

        if hasattr(self, "statusLabel"):

            self.statusLabel.setText(
                "Operazione in corso..."
                if busy
                else "Pronto"
            )

    # =====================================================
    # WORKER
    # =====================================================

    def _start_worker(self, task, args):

        if self._busy:
            return

        self._set_busy(True)

        self._thread = QThread(self)

        self._worker = TranslationBuilderWorker(
            task,
            args,
        )

        self._worker.moveToThread(
            self._thread
        )

        self._thread.started.connect(
            self._worker.run
        )

        self._worker.progress.connect(
            self._on_worker_progress
        )

        self._worker.log_message.connect(
            self.log
        )

        self._worker.preview_message.connect(
            self._append_preview
        )

        self._worker.finished.connect(
            self._on_worker_finished
        )

        self._worker.failed.connect(
            self._on_worker_failed
        )

        self._worker.finished.connect(
            self._thread.quit
        )

        self._worker.failed.connect(
            self._thread.quit
        )

        self._thread.finished.connect(
            self._cleanup_worker
        )

        self._thread.start()

    def _on_worker_progress(
        self,
        value,
        text,
    ):

        value = max(
            0,
            min(
                100,
                int(value),
            ),
        )

        if hasattr(self, "progressBar"):
            self.progressBar.setValue(value)

        if hasattr(self, "statusLabel"):
            self.statusLabel.setText(str(text))

    def _append_preview(self, text):

        if not hasattr(self, "txtPreview"):
            return

        if text == "__CLEAR__":
            self.txtPreview.clear()
            return

        self.txtPreview.append(str(text))

    def _on_worker_finished(self, result):

        if hasattr(self, "progressBar"):
            self.progressBar.setValue(100)

        self._set_busy(False)

        if (
            isinstance(result, dict)
            and result.get("message")
        ):

            QMessageBox.information(
                self,
                "Completato",
                result["message"],
            )

    def _on_worker_failed(self, error):

        self._set_busy(False)

        if hasattr(self, "progressBar"):
            self.progressBar.setValue(0)

        first_line = (
            error.splitlines()[0]
            if error
            else "Errore sconosciuto."
        )

        self.log(
            "ERRORE: " + first_line
        )

        QMessageBox.critical(
            self,
            "Errore",
            "Operazione non riuscita.\n\n"
            "Controlla il log per i dettagli.",
        )

    def _cleanup_worker(self):

        if self._worker is not None:
            self._worker.deleteLater()

        if self._thread is not None:
            self._thread.deleteLater()

        self._worker = None
        self._thread = None

    # =====================================================
    # UTILITY
    # =====================================================

    def log(self, message):

        if hasattr(self, "txtLog"):
            self.txtLog.append(str(message))

    def clear_ui(self):

        if self._busy:
            return

        fields = (
            "txtPluginFolder",
            "txtI18nFolder",
            "txtPreview",
            "txtLog",
        )

        for name in fields:

            if hasattr(self, name):
                getattr(self, name).clear()

    # =====================================================
    # FOLDERS
    # =====================================================

    def select_plugin_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleziona cartella plugin",
        )

        if not folder:
            return

        folder = os.path.normpath(folder)

        if hasattr(self, "txtPluginFolder"):
            self.txtPluginFolder.setText(folder)

        i18n = os.path.join(
            folder,
            "i18n",
        )

        if (
            os.path.isdir(i18n)
            and hasattr(self, "txtI18nFolder")
        ):

            self.txtI18nFolder.setText(
                i18n.replace("\\", "/")
            )

    def select_i18n_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleziona cartella i18n",
        )

        if folder and hasattr(
            self,
            "txtI18nFolder",
        ):

            self.txtI18nFolder.setText(
                os.path.normpath(folder).replace(
                    "\\",
                    "/",
                )
            )

    def select_lrelease(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona lrelease",
            "",
            "Eseguibili (*)",
        )

        if not path:
            return

        if hasattr(self, "txtLreleasePath"):
            self.txtLreleasePath.setText(path)

        QSettings().setValue(
            "translation_builder/lrelease_path",
            path,
        )

    # =====================================================
    # ARGOS IMPORT
    # =====================================================

    @staticmethod
    def _import_argos():

        try:

            import argostranslate.package
            import argostranslate.translate

            return (
                argostranslate.package,
                argostranslate.translate,
            )

        except ImportError:

            return None, None

    # =====================================================
    # ARGOS STATUS
    # =====================================================

    def check_argos(self):

        package_module, translate_module = (
            self._import_argos()
        )

        if (
            package_module is None
            or translate_module is None
        ):

            if hasattr(
                self,
                "txtArgosStatus",
            ):

                self.txtArgosStatus.setPlainText(
                    "Argos Translate non installato.\n\n"
                    "Installazione opzionale:\n\n"
                    "python -m pip install argostranslate"
                )

            if hasattr(
                self,
                "btnInstallArgos",
            ):

                self.btnInstallArgos.setEnabled(False)

            return False

        try:

            languages = (
                translate_module.get_installed_languages()
            )

            codes = sorted(
                language.code
                for language in languages
            )

            if not codes:

                message = (
                    "Argos Translate installato.\n\n"
                    "Nessun modello linguistico installato.\n\n"
                    "Inserisci le lingue, ad esempio "
                    "'it, en', quindi premi "
                    "'Installa modelli'."
                )

            else:

                message = (
                    "Argos Translate installato.\n\n"
                    "Lingue disponibili:\n"
                    + ", ".join(codes)
                )

            if hasattr(
                self,
                "txtArgosStatus",
            ):

                self.txtArgosStatus.setPlainText(
                    message
                )

            if hasattr(
                self,
                "btnInstallArgos",
            ):

                self.btnInstallArgos.setEnabled(True)

            return True

        except Exception as error:

            if hasattr(
                self,
                "txtArgosStatus",
            ):

                self.txtArgosStatus.setPlainText(
                    "Argos Translate installato, "
                    "ma non è stato possibile leggere "
                    "i modelli.\n\n"
                    f"{error}"
                )

            if hasattr(
                self,
                "btnInstallArgos",
            ):

                self.btnInstallArgos.setEnabled(True)

            return True

    # =====================================================
    # LANGUAGE NORMALIZATION
    # =====================================================

    @staticmethod
    def _normalize_language(language):

        language = str(
            language or ""
        ).strip().lower()

        mapping = {
            "it": "it",
            "ita": "it",
            "italiano": "it",

            "en": "en",
            "eng": "en",
            "inglese": "en",

            "fr": "fr",
            "fra": "fr",
            "francese": "fr",

            "de": "de",
            "deu": "de",
            "tedesco": "de",

            "es": "es",
            "spa": "es",
            "spagnolo": "es",

            "pt": "pt",
            "por": "pt",
            "portoghese": "pt",

            "nl": "nl",
            "nld": "nl",
            "olandese": "nl",

            "ru": "ru",
            "russo": "ru",

            "uk": "uk",
            "ucraino": "uk",

            "pl": "pl",
            "polacco": "pl",

            "ja": "ja",
            "giapponese": "ja",

            "zh": "zh",
            "cinese": "zh",

            "ko": "ko",
            "coreano": "ko",

            "tr": "tr",
            "turco": "tr",

            "ar": "ar",
            "arabo": "ar",

            "cs": "cs",
            "ceco": "cs",

            "el": "el",
            "greco": "el",

            "hu": "hu",
            "ungherese": "hu",

            "ro": "ro",
            "rumeno": "ro",

            "sk": "sk",
            "sl": "sl",
            "bg": "bg",

            "sv": "sv",
            "svedese": "sv",

            "da": "da",
            "danese": "da",

            "fi": "fi",
            "finlandese": "fi",

            "nb": "nb",
            "no": "nb",
            "norvegese": "nb",
        }

        return mapping.get(
            language,
            language,
        )

    @staticmethod
    def _parse_languages(text):

        languages = []

        for value in str(text or "").split(","):

            value = value.strip()

            if not value:
                continue

            language = (
                TranslationBuilderDialog
                ._normalize_language(value)
            )

            if language and language not in languages:
                languages.append(language)

        return languages

    # =====================================================
    # ARGOS MODEL INSTALLATION
    # =====================================================

    def install_argos_models(self):

        if not hasattr(
            self,
            "txtLanguages",
        ):
            return

        languages = self._parse_languages(
            self.txtLanguages.text()
        )

        if len(languages) < 2:

            QMessageBox.warning(
                self,
                "Argos Translate",
                "Inserisci almeno una lingua sorgente "
                "e una lingua di destinazione.\n\n"
                "Esempio: it, en",
            )

            return

        package_module, translate_module = (
            self._import_argos()
        )

        if package_module is None:

            QMessageBox.warning(
                self,
                "Argos Translate",
                "Argos Translate non è installato.\n\n"
                "Installa prima:\n\n"
                "python -m pip install argostranslate",
            )

            return

        QSettings().setValue(
            "translation_builder/languages",
            self.txtLanguages.text().strip(),
        )

        self._start_worker(
            self._install_argos_models_task,
            (languages,),
        )

    def _install_argos_models_task(
        self,
        languages,
        log_callback=None,
        progress_callback=None,
        preview_callback=None,
    ):

        log = (
            log_callback
            or (lambda message: None)
        )

        progress = (
            progress_callback
            or (lambda value, text: None)
        )

        package_module, translate_module = (
            self._import_argos()
        )

        if package_module is None:

            raise RuntimeError(
                "Argos Translate non installato."
            )

        source = languages[0]
        targets = languages[1:]

        log(
            "Aggiornamento indice pacchetti Argos..."
        )

        progress(
            5,
            "Aggiornamento indice Argos...",
        )

        package_module.update_package_index()

        available_packages = (
            package_module.get_available_packages()
        )

        log(
            "Pacchetti disponibili: "
            f"{len(available_packages)}"
        )

        total = len(targets)

        for index, target in enumerate(targets):

            if source == target:

                log(
                    f"{source} -> {target}: ignorato."
                )

                continue

            installed_languages = (
                translate_module.get_installed_languages()
            )

            from_lang = next(
                (
                    language
                    for language in installed_languages
                    if language.code == source
                ),
                None,
            )

            to_lang = next(
                (
                    language
                    for language in installed_languages
                    if language.code == target
                ),
                None,
            )

            existing_translation = None

            if (
                from_lang is not None
                and to_lang is not None
            ):

                try:

                    existing_translation = (
                        from_lang.get_translation(
                            to_lang
                        )
                    )

                except (
                    AttributeError,
                    RuntimeError,
                    TypeError,
                ) as error:

                    log(
                        f"Impossibile verificare "
                        f"{source} -> {target}: "
                        f"{error}"
                    )

            if existing_translation is not None:

                log(
                    f"Modello {source} -> {target} "
                    "già installato."
                )

                continue

            package = next(
                (
                    item
                    for item in available_packages
                    if item.from_code == source
                    and item.to_code == target
                ),
                None,
            )

            if package is None:

                log(
                    f"Modello diretto "
                    f"{source} -> {target} "
                    "non trovato."
                )

                continue

            log(
                f"Download modello "
                f"{source} -> {target}..."
            )

            progress(
                int(
                    10
                    + index * 80
                    / max(1, total)
                ),
                f"Download modello "
                f"{source} -> {target}...",
            )

            download_path = package.download()

            log(
                f"Installazione modello "
                f"{source} -> {target}..."
            )

            package_module.install_from_path(
                download_path
            )

            log(
                f"Modello {source} -> "
                f"{target} installato."
            )

        progress(
            100,
            "Modelli Argos pronti.",
        )

        return {
            "message":
                "Installazione modelli Argos completata."
        }

    # =====================================================
    # ARGOS TRANSLATION
    # =====================================================

    def _get_argos_translation(
        self,
        source_lang,
        target_lang,
    ):

        _, translate_module = (
            self._import_argos()
        )

        if translate_module is None:

            raise RuntimeError(
                "Argos Translate non installato."
            )

        source = self._normalize_language(
            source_lang
        )

        target = self._normalize_language(
            target_lang
        )

        installed_languages = (
            translate_module.get_installed_languages()
        )

        from_lang = next(
            (
                language
                for language in installed_languages
                if language.code == source
            ),
            None,
        )

        to_lang = next(
            (
                language
                for language in installed_languages
                if language.code == target
            ),
            None,
        )

        if from_lang is None:

            raise RuntimeError(
                f"Lingua sorgente '{source}' "
                "non installata in Argos."
            )

        if to_lang is None:

            raise RuntimeError(
                f"Lingua destinazione '{target}' "
                "non installata in Argos."
            )

        try:

            translation = (
                from_lang.get_translation(
                    to_lang
                )
            )

        except (
            AttributeError,
            RuntimeError,
            TypeError,
        ) as error:

            raise RuntimeError(
                f"Modello Argos {source} -> "
                f"{target} non disponibile: {error}"
            ) from error

        if translation is None:

            raise RuntimeError(
                f"Modello Argos "
                f"{source} -> {target} "
                "non installato."
            )

        return translation

    # =====================================================
    # QT PLACEHOLDERS
    # =====================================================

    @staticmethod
    def _protect_qt_placeholders(text):

        placeholders = []

        patterns = (
            r"%\d+",
            r"%n",
            r"\$\{[^}]+\}",
            r"\{[A-Za-z_][A-Za-z0-9_.-]*\}",
        )

        pattern = "|".join(patterns)

        def replace(match):

            index = len(placeholders)

            token = (
                f"__QT_PLACEHOLDER_{index}__"
            )

            placeholders.append(
                (
                    token,
                    match.group(0),
                )
            )

            return token

        protected = re.sub(
            pattern,
            replace,
            text,
        )

        return protected, placeholders

    @staticmethod
    def _restore_qt_placeholders(
        text,
        placeholders,
    ):

        result = text

        for token, original in placeholders:

            result = result.replace(
                token,
                original,
            )

        return result

    # =====================================================
    # AUTO TRANSLATION
    # =====================================================

    def _auto_translate_texts(
        self,
        texts,
        source_lang,
        target_lang,
        log_callback=None,
        progress_callback=None,
    ):

        log = (
            log_callback
            or (lambda message: None)
        )

        progress = (
            progress_callback
            or (lambda value, text: None)
        )

        unique_texts = list(
            dict.fromkeys(
                text
                for text in texts
                if text and text.strip()
            )
        )

        if not unique_texts:
            return {}

        source = self._normalize_language(
            source_lang
        )

        target = self._normalize_language(
            target_lang
        )

        total = len(unique_texts)

        log(
            f"Argos Translate: "
            f"{source} -> {target} "
            f"({total} stringhe)"
        )

        translation = (
            self._get_argos_translation(
                source,
                target,
            )
        )

        translations = {}

        for index, text in enumerate(
            unique_texts
        ):

            protected, placeholders = (
                self._protect_qt_placeholders(
                    text
                )
            )

            result = translation.translate(
                protected
            )

            result = (
                self._restore_qt_placeholders(
                    result,
                    placeholders,
                )
            )

            translations[text] = result

            done = index + 1

            progress(
                int(done * 100 / total),
                f"Argos {source} -> "
                f"{target}: "
                f"{done}/{total}",
            )

            if done % 10 == 0 or done == total:

                log(
                    f"Argos: tradotte "
                    f"{done}/{total} stringhe."
                )

        return translations

    # =====================================================
    # STRING REGISTRY
    # =====================================================

    @staticmethod
    def _register_string(
        results,
        context,
        source,
        filename,
        comment=None,
        line=None,
    ):

        context = (
            str(context or "").strip()
            or os.path.splitext(
                os.path.basename(filename)
            )[0]
        )

        source = str(source or "")

        key = (
            context,
            source,
        )

        entry = results.get(key)

        if entry is None:

            entry = {
                "locations": [],
                "comment": comment or "",
            }

            results[key] = entry

        location = {
            "filename": filename,
            "line": line,
        }

        if location not in entry["locations"]:

            entry["locations"].append(
                location
            )

        if (
            comment
            and not entry["comment"]
        ):

            entry["comment"] = comment

    # =====================================================
    # AST HELPERS
    # =====================================================

    @staticmethod
    def _literal_string(node):

        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):

            return node.value

        if isinstance(node, ast.Str):

            return node.s

        return None

    # =====================================================
    # PYTHON TRANSLATION CALLS
    # =====================================================

    def _python_call_translation(
        self,
        node,
        class_context,
        module_context,
    ):

        if not isinstance(node, ast.Call):
            return None

        # -------------------------------------------------
        # tr(), _tr()
        # -------------------------------------------------

        if isinstance(node.func, ast.Name):

            function_name = node.func.id

            if function_name in (
                "tr",
                "_tr",
            ):

                if not node.args:
                    return None

                source = self._literal_string(
                    node.args[0]
                )

                if source is None or not source:
                    return None

                comment = None

                if len(node.args) >= 2:

                    comment = (
                        self._literal_string(
                            node.args[1]
                        )
                    )

                return (
                    class_context
                    or module_context,
                    source,
                    comment,
                )

            if function_name == "_translate":

                if len(node.args) < 2:
                    return None

                context = self._literal_string(
                    node.args[0]
                )

                source = self._literal_string(
                    node.args[1]
                )

                if (
                    context is None
                    or source is None
                    or not source
                ):
                    return None

                comment = None

                if len(node.args) >= 3:

                    comment = (
                        self._literal_string(
                            node.args[2]
                        )
                    )

                return (
                    context,
                    source,
                    comment,
                )

        # -------------------------------------------------
        # self.tr(), self._tr(), object.tr()
        # -------------------------------------------------

        if isinstance(node.func, ast.Attribute):

            function_name = node.func.attr

            if function_name in (
                "tr",
                "_tr",
            ):

                if not node.args:
                    return None

                source = self._literal_string(
                    node.args[0]
                )

                if source is None or not source:
                    return None

                comment = None

                if len(node.args) >= 2:

                    comment = (
                        self._literal_string(
                            node.args[1]
                        )
                    )

                return (
                    class_context
                    or module_context,
                    source,
                    comment,
                )

            # -------------------------------------------------
            # QCoreApplication.translate(...)
            # QObject.translate(...)
            # QtCore.QCoreApplication.translate(...)
            # -------------------------------------------------

            if function_name == "translate":

                if len(node.args) < 2:
                    return None

                context = self._literal_string(
                    node.args[0]
                )

                source = self._literal_string(
                    node.args[1]
                )

                if (
                    context is None
                    or source is None
                    or not source
                ):
                    return None

                comment = None

                if len(node.args) >= 3:

                    comment = (
                        self._literal_string(
                            node.args[2]
                        )
                    )

                return (
                    context,
                    source,
                    comment,
                )

        return None

    # =====================================================
    # PYTHON SCAN
    # =====================================================

    def scan_files(self, root_folder):

        results = {}
        scanned_files = []

        for root, dirs, files in os.walk(
            root_folder
        ):

            dirs.sort()

            for filename in sorted(files):

                if not filename.lower().endswith(".py"):
                    continue

                path = os.path.join(
                    root,
                    filename,
                )

                rel_path = (
                    os.path.relpath(
                        path,
                        root_folder,
                    )
                    .replace("\\", "/")
                )

                scanned_files.append(rel_path)

                try:

                    with tokenize.open(path) as file:

                        content = file.read()

                    tree = ast.parse(
                        content,
                        filename=path,
                    )

                except (
                    OSError,
                    SyntaxError,
                    UnicodeError,
                    ValueError,
                ) as error:

                    continue

                module_context = (
                    os.path.splitext(filename)[0]
                )

                class_stack = []

                dialog = self

                class Visitor(ast.NodeVisitor):

                    def visit_ClassDef(
                        visitor_self,
                        node,
                    ):

                        class_stack.append(
                            node.name
                        )

                        visitor_self.generic_visit(
                            node
                        )

                        class_stack.pop()

                    def visit_Call(
                        visitor_self,
                        node,
                    ):

                        class_context = (
                            class_stack[-1]
                            if class_stack
                            else module_context
                        )

                        found = (
                            dialog._python_call_translation(
                                node,
                                class_context,
                                module_context,
                            )
                        )

                        if found:

                            (
                                context,
                                source,
                                comment,
                            ) = found

                            dialog._register_string(
                                results,
                                context,
                                source,
                                rel_path,
                                comment,
                                getattr(
                                    node,
                                    "lineno",
                                    None,
                                ),
                            )

                        visitor_self.generic_visit(node)

                Visitor().visit(tree)

        self._last_py_files = scanned_files

        return results

    # =====================================================
    # UI SCAN
    # =====================================================

    def scan_ui_strings(self, root_folder):

        results = {}
        scanned_files = []

        for root, dirs, files in os.walk(
            root_folder
        ):

            dirs.sort()

            for filename in sorted(files):

                if not filename.lower().endswith(".ui"):
                    continue

                full_path = os.path.join(
                    root,
                    filename,
                )

                rel_path = (
                    os.path.relpath(
                        full_path,
                        root_folder,
                    )
                    .replace("\\", "/")
                )

                scanned_files.append(rel_path)

                self.extract_strings_from_ui(
                    full_path,
                    rel_path,
                    results,
                )

        self._last_ui_files = scanned_files

        return results

    def extract_strings_from_ui(
        self,
        full_path,
        rel_path,
        results,
    ):

        try:

            root = _safe_xml_from_file(
                full_path
            )

        except (
            OSError,
            xml_safe.XmlParseError,
            UnicodeError,
        ):

            return

        class_el = root.find("class")

        if class_el is not None:

            context = (
                class_el.text or ""
            ).strip()

        else:

            context = os.path.splitext(
                os.path.basename(full_path)
            )[0]

        if not context:

            context = os.path.splitext(
                os.path.basename(full_path)
            )[0]

        for string_el in root.iter("string"):

            if (
                string_el.get(
                    "notr",
                    "",
                ).lower()
                == "true"
            ):

                continue

            text = string_el.text or ""

            if not text.strip():
                continue

            comment = (
                string_el.get("comment")
                or string_el.get("extracomment")
                or None
            )

            self._register_string(
                results,
                context,
                text,
                rel_path,
                comment,
            )

    # =====================================================
    # MERGE REGISTRIES
    # =====================================================

    @staticmethod
    def _merge_results(*registries):

        merged = {}

        for registry in registries:

            for key, entry in registry.items():

                if key not in merged:

                    merged[key] = {
                        "locations": list(
                            entry.get(
                                "locations",
                                [],
                            )
                        ),
                        "comment": entry.get(
                            "comment",
                            "",
                        ),
                    }

                    continue

                target = merged[key]

                for location in entry.get(
                    "locations",
                    [],
                ):

                    if location not in target[
                        "locations"
                    ]:

                        target["locations"].append(
                            location
                        )

                if (
                    entry.get("comment")
                    and not target.get("comment")
                ):

                    target["comment"] = (
                        entry["comment"]
                    )

        return merged

    # =====================================================
    # TS TRANSLATIONS
    # =====================================================

    def _apply_translations_to_ts(
        self,
        ts_path,
        translations,
        log_callback,
    ):

        if not os.path.isfile(ts_path):
            return

        try:

            root = _safe_xml_from_file(
                ts_path
            )

        except (
            OSError,
            xml_safe.XmlParseError,
            UnicodeError,
        ) as error:

            raise RuntimeError(
                f"Impossibile leggere {ts_path}: "
                f"{error}"
            ) from error

        changed = 0

        for context in root.findall("context"):

            for message in context.findall("message"):

                source = message.find("source")
                translation = message.find(
                    "translation"
                )

                if (
                    source is None
                    or translation is None
                ):
                    continue

                source_text = source.text or ""

                translated = translations.get(
                    source_text
                )

                if not translated:
                    continue

                translation.text = translated

                translation.attrib.pop(
                    "type",
                    None,
                )

                changed += 1

        tree = root

        _write_xml_tree(
            tree,
            ts_path,
        )

        log_callback(
            f"Aggiornato {ts_path}: "
            f"{changed} traduzioni."
        )

    # =====================================================
    # GENERATE TS
    # =====================================================

    def generate_ts(self):

        plugin_folder = (
            self.txtPluginFolder.text().strip()
        )

        i18n_folder = (
            self.txtI18nFolder.text().strip()
        )

        languages = self._parse_languages(
            self.txtLanguages.text()
        )

        if not os.path.isdir(plugin_folder):

            QMessageBox.warning(
                self,
                "Errore",
                "Cartella plugin non valida.",
            )

            return

        if len(languages) < 2:

            QMessageBox.warning(
                self,
                "Errore",
                "Inserire almeno lingua sorgente "
                "e una lingua di destinazione.\n\n"
                "Esempio: it, en",
            )

            return

        os.makedirs(
            i18n_folder,
            exist_ok=True,
        )

        QSettings().setValue(
            "translation_builder/languages",
            self.txtLanguages.text().strip(),
        )

        self._start_worker(
            self._generate_ts_task,
            (
                plugin_folder,
                i18n_folder,
                languages,
            ),
        )

    # =====================================================
    # TS TASK
    # =====================================================

    def _generate_ts_task(
        self,
        plugin_folder,
        i18n_folder,
        languages,
        log_callback=None,
        progress_callback=None,
        preview_callback=None,
    ):

        log = (
            log_callback
            or (lambda message: None)
        )

        progress = (
            progress_callback
            or (lambda value, text: None)
        )

        preview = (
            preview_callback
            or (lambda text: None)
        )

        os.makedirs(
            i18n_folder,
            exist_ok=True,
        )

        plugin_name = os.path.basename(
            os.path.normpath(
                plugin_folder
            )
        )

        source_lang = self._normalize_language(
            languages[0]
        )

        target_langs = [
            self._normalize_language(language)
            for language in languages[1:]
        ]

        # -------------------------------------------------
        # PYTHON
        # -------------------------------------------------

        log("Scansione file Python...")

        progress(
            5,
            "Scansione file Python...",
        )

        py_strings = self.scan_files(
            plugin_folder
        )

        py_files = getattr(
            self,
            "_last_py_files",
            [],
        )

        log(
            f"File Python analizzati: "
            f"{len(py_files)}"
        )

        # -------------------------------------------------
        # UI
        # -------------------------------------------------

        log("Scansione file UI...")

        progress(
            25,
            "Scansione file UI...",
        )

        ui_strings = self.scan_ui_strings(
            plugin_folder
        )

        ui_files = getattr(
            self,
            "_last_ui_files",
            [],
        )

        log(
            f"File UI analizzati: "
            f"{len(ui_files)}"
        )

        # -------------------------------------------------
        # MERGE
        # -------------------------------------------------

        merged = self._merge_results(
            py_strings,
            ui_strings,
        )

        if not merged:

            log(
                "Nessuna stringa traducibile trovata."
            )

            return {
                "message":
                    "Nessuna stringa traducibile trovata."
            }

        # -------------------------------------------------
        # PREVIEW
        # -------------------------------------------------

        preview("__CLEAR__")

        contexts = {}

        for (
            context,
            source,
        ), entry in merged.items():

            contexts.setdefault(
                context,
                [],
            ).append(
                {
                    "source": source,
                    "locations": entry[
                        "locations"
                    ],
                    "comment": entry[
                        "comment"
                    ],
                }
            )

            filenames = sorted(
                set(
                    location["filename"]
                    for location in entry[
                        "locations"
                    ]
                )
            )

            preview(
                f"[{context}] "
                f"{source} "
                f"({', '.join(filenames)})"
            )

        all_source_texts = [
            item["source"]
            for items in contexts.values()
            for item in items
        ]

        # =================================================
        # GENERATE ALL TS FIRST
        # =================================================

        progress(
            40,
            "Generazione file TS...",
        )

        generated_ts = []

        for language in languages:

            normalized_lang = (
                self._normalize_language(
                    language
                )
            )

            ts_path = os.path.join(
                i18n_folder,
                f"{plugin_name}_{normalized_lang}.ts",
            )

            log(
                f"Generazione: {ts_path}"
            )

            ts_root = xml_safe.Element(
                "TS",
                {
                    "version": "2.1",
                    "language": normalized_lang,
                },
            )

            for (
                context_name,
                items,
            ) in contexts.items():

                context_el = xml_safe.sub_element(
                    ts_root,
                    "context",
                )

                name_el = xml_safe.sub_element(
                    context_el,
                    "name",
                )

                name_el.text = context_name

                for item in items:

                    message_el = xml_safe.sub_element(
                        context_el,
                        "message",
                    )

                    # -------------------------------------
                    # LOCATIONS
                    # -------------------------------------

                    for location in item[
                        "locations"
                    ]:

                        location_el = (
                            xml_safe.sub_element(
                                message_el,
                                "location",
                            )
                        )

                        location_el.set(
                            "filename",
                            location["filename"],
                        )

                        if location.get("line"):

                            location_el.set(
                                "line",
                                str(
                                    location["line"]
                                ),
                            )

                    # -------------------------------------
                    # SOURCE
                    # -------------------------------------

                    source_el = xml_safe.sub_element(
                        message_el,
                        "source",
                    )

                    source_el.text = item["source"]

                    # -------------------------------------
                    # COMMENT
                    # -------------------------------------

                    if item["comment"]:

                        comment_el = (
                            xml_safe.sub_element(
                                message_el,
                                "translatorcomment",
                            )
                        )

                        comment_el.text = (
                            item["comment"]
                        )

                    # -------------------------------------
                    # TRANSLATION
                    # -------------------------------------

                    translation_el = (
                        xml_safe.sub_element(
                            message_el,
                            "translation",
                        )
                    )

                    if normalized_lang == source_lang:

                        translation_el.text = (
                            item["source"]
                        )

                    else:

                        translation_el.text = ""

                        translation_el.set(
                            "type",
                            "unfinished",
                        )

            _write_xml_tree(
                ts_root,
                ts_path,
            )

            generated_ts.append(
                ts_path
            )

            log(
                f"TS creato: {ts_path}"
            )

        # =================================================
        # ARGOS IS OPTIONAL
        # =================================================

        package_module, translate_module = (
            self._import_argos()
        )

        if (
            package_module is None
            or translate_module is None
        ):

            log(
                "Argos Translate non installato."
            )

            log(
                "I file TS sono stati comunque creati."
            )

            progress(
                100,
                "TS pronti.",
            )

            return {
                "message":
                    "File TS creati con successo.\n\n"
                    "Argos Translate non è installato; "
                    "le traduzioni automatiche non sono "
                    "state eseguite."
            }

        # =================================================
        # AUTOMATIC TRANSLATION
        # =================================================

        total_languages = len(target_langs)

        for index, lang in enumerate(
            target_langs
        ):

            log(
                f"Traduzione Argos "
                f"{source_lang} -> {lang}..."
            )

            try:

                def update_progress(
                    value,
                    text,
                    idx=index,
                ):

                    base = 50
                    available = 45

                    offset = int(
                        idx
                        * available
                        / max(
                            1,
                            total_languages,
                        )
                    )

                    portion = int(
                        value
                        * available
                        / max(
                            1,
                            total_languages,
                        )
                    )

                    progress(
                        min(
                            95,
                            base
                            + offset
                            + portion,
                        ),
                        text,
                    )

                translations = (
                    self._auto_translate_texts(
                        all_source_texts,
                        source_lang,
                        lang,
                        log_callback=log,
                        progress_callback=
                            update_progress,
                    )
                )

                ts_path = os.path.join(
                    i18n_folder,
                    f"{plugin_name}_{lang}.ts",
                )

                self._apply_translations_to_ts(
                    ts_path,
                    translations,
                    log,
                )

            except Exception as error:

                log(
                    f"ATTENZIONE: impossibile "
                    f"tradurre "
                    f"{source_lang} -> {lang}: "
                    f"{error}"
                )

                log(
                    "Il file TS è comunque disponibile "
                    "per la modifica manuale."
                )

        progress(
            100,
            "TS pronti.",
        )

        log(
            "File TS generati con successo."
        )

        return {
            "message":
                "File TS generati con successo."
        }

    # =====================================================
    # LRELEASE
    # =====================================================

    def autodetect_lrelease(self):

        candidates = []

        if os.name == "nt":

            candidates.extend(
                [
                    r"C:\Program Files\QGIS 4.2.1\apps\Qt6\bin\lrelease.exe",
                    r"C:\Program Files\QGIS 4.2.1\apps\Qt\bin\lrelease.exe",
                    r"C:\OSGeo4W\bin\lrelease.exe",
                ]
            )

        elif sys.platform == "darwin":

            candidates.extend(
                [
                    "/Applications/QGIS.app/Contents/MacOS/bin/lrelease",
                    "/usr/local/bin/lrelease",
                    "/usr/bin/lrelease",
                ]
            )

        else:

            candidates.extend(
                [
                    "/usr/bin/lrelease",
                    "/usr/local/bin/lrelease",
                ]
            )

        for path in candidates:

            if os.path.isfile(path):
                return path

        return shutil.which(
            "lrelease"
        ) or ""

    def get_lrelease_path(self):

        configured = str(
            QSettings().value(
                "translation_builder/lrelease_path",
                "",
            )
            or ""
        ).strip()

        if (
            configured
            and os.path.isfile(configured)
        ):

            return configured

        return self.autodetect_lrelease()

    # =====================================================
    # GENERATE QM
    # =====================================================

    def generate_qm(self):

        i18n_folder = (
            self.txtI18nFolder.text().strip()
        )

        if not os.path.isdir(i18n_folder):

            QMessageBox.warning(
                self,
                "Errore",
                "Cartella i18n non valida.",
            )

            return

        ts_files = sorted(
            filename
            for filename in os.listdir(
                i18n_folder
            )
            if filename.lower().endswith(".ts")
        )

        if not ts_files:

            QMessageBox.warning(
                self,
                "Errore",
                "Nessun file TS trovato.",
            )

            return

        lrelease = self.get_lrelease_path()

        if not lrelease:

            QMessageBox.warning(
                self,
                "Errore",
                "lrelease non trovato.\n\n"
                "Seleziona manualmente "
                "il file lrelease.",
            )

            return

        if hasattr(
            self,
            "txtLreleasePath",
        ):

            self.txtLreleasePath.setText(
                lrelease
            )

        QSettings().setValue(
            "translation_builder/lrelease_path",
            lrelease,
        )

        self._start_worker(
            self._generate_qm_task,
            (
                i18n_folder,
                lrelease,
            ),
        )

    def _generate_qm_task(
        self,
        i18n_folder,
        lrelease_path,
        log_callback=None,
        progress_callback=None,
        preview_callback=None,
    ):

        log = (
            log_callback
            or (lambda message: None)
        )

        progress = (
            progress_callback
            or (lambda value, text: None)
        )

        ts_files = sorted(
            filename
            for filename in os.listdir(
                i18n_folder
            )
            if filename.lower().endswith(".ts")
        )

        total = len(ts_files)

        if total == 0:

            raise RuntimeError(
                "Nessun file TS trovato."
            )

        for index, filename in enumerate(
            ts_files
        ):

            ts_path = os.path.abspath(
                os.path.join(
                    i18n_folder,
                    filename,
                )
            )

            qm_path = (
                os.path.splitext(
                    ts_path
                )[0]
                + ".qm"
            )

            log(
                f"Compilazione: {filename}"
            )

            process = QProcess()

            process.setWorkingDirectory(
                i18n_folder
            )

            process.start(
                lrelease_path,
                [
                    ts_path,
                    "-qm",
                    qm_path,
                ],
            )

            if not process.waitForStarted(
                5000
            ):

                raise RuntimeError(
                    "Impossibile avviare lrelease:\n"
                    f"{lrelease_path}"
                )

            if not process.waitForFinished(
                60000
            ):

                process.kill()
                process.waitForFinished(3000)

                raise RuntimeError(
                    "Timeout durante la compilazione "
                    f"di {filename}."
                )

            stdout = bytes(
                process.readAllStandardOutput()
            ).decode(
                "utf-8",
                errors="replace",
            )

            stderr = bytes(
                process.readAllStandardError()
            ).decode(
                "utf-8",
                errors="replace",
            )

            if stdout.strip():
                log(stdout.strip())

            if stderr.strip():
                log(stderr.strip())

            exit_code = process.exitCode()

            if exit_code != 0:

                raise RuntimeError(
                    f"lrelease ha restituito "
                    f"il codice {exit_code} "
                    f"per {filename}."
                )

            if not os.path.isfile(qm_path):

                raise RuntimeError(
                    "Il file QM non è stato creato:\n"
                    f"{qm_path}"
                )

            log(
                f"Creato: {qm_path}"
            )

            progress(
                int(
                    (index + 1)
                    * 100
                    / total
                ),
                f"Generazione QM: "
                f"{index + 1}/{total}",
            )

        return {
            "message":
                "File QM generati con successo."
        }

    # =====================================================
    # QT LINGUIST
    # =====================================================

    def autodetect_linguist(self):

        candidates = []

        if os.name == "nt":

            candidates.extend(
                [
                    r"C:\Program Files\QGIS 4.2.1\apps\Qt6\bin\linguist.exe",
                    r"C:\Program Files\QGIS 4.2.1\apps\Qt\bin\linguist.exe",
                    r"C:\OSGeo4W\bin\linguist.exe",
                ]
            )

        elif sys.platform == "darwin":

            candidates.extend(
                [
                    "/Applications/QGIS.app/Contents/MacOS/bin/linguist",
                    "/usr/local/bin/linguist",
                    "/usr/bin/linguist",
                ]
            )

        else:

            candidates.extend(
                [
                    "/usr/bin/linguist",
                    "/usr/local/bin/linguist",
                ]
            )

        for path in candidates:

            if os.path.isfile(path):
                return path

        return shutil.which(
            "linguist"
        ) or ""

    def get_linguist_path(self):

        return self.autodetect_linguist()

    def open_linguist(self):

        linguist = self.get_linguist_path()

        if not linguist:

            path, _ = QFileDialog.getOpenFileName(
                self,
                "Seleziona Qt Linguist",
                "",
                "Eseguibili (*)",
            )

            if not path:
                return

            linguist = path

        process = QProcess(self)

        if not process.startDetached(
            linguist,
            [],
        ):

            QMessageBox.warning(
                self,
                "Errore",
                "Impossibile avviare Qt Linguist.",
            )
