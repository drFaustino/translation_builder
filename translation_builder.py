import os
import re
# Parsing sicuro
from defusedxml.ElementTree import parse as safe_parse

# Creazione XML (sicura perché non coinvolge input esterno)
import xml.etree.ElementTree as ET


from qgis.PyQt.QtWidgets import (
    QAction, QDialog, QFileDialog, QMessageBox
)
from qgis.PyQt.QtCore import (
    QCoreApplication, QSettings, QTranslator, QProcess
)
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon


# ---------------------------------------------------------
# Caricamento UI
# ---------------------------------------------------------

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui", "translation_builder_dialog.ui")
)


# ---------------------------------------------------------
# Plugin principale
# ---------------------------------------------------------

class TranslationBuilder:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Caricamento traduzioni
        locale = QSettings().value("locale/userLocale", "it")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "resources", "i18n", f"translation_builder_{locale}.qm"
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = QCoreApplication.translate(
            "TranslationBuilderDialog", "&Translation Builder"
        )

        self.dlg = None

    # ---------------------------------------------------------
    # GUI
    # ---------------------------------------------------------

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "resources", "images", "icon.png")

        self.action = QAction(
            QIcon(icon_path),
            QCoreApplication.translate(
                "TranslationBuilderDialog", "Translation Builder"
            ),
            self.iface.mainWindow()
        )

        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)

    # ---------------------------------------------------------
    # Apertura dialog
    # ---------------------------------------------------------

    def run(self):
        if self.dlg is None:
            self.dlg = TranslationBuilderDialog(self.iface)
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

# ---------------------------------------------------------
# Dialog principale
# ---------------------------------------------------------

class TranslationBuilderDialog(QDialog, FORM_CLASS):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)

        # Carica percorso salvato di lrelease.exe
        settings = QSettings()
        self.txtLreleasePath.setText(
            settings.value("translation_builder/lrelease_path", "")
        )

        # Regex per QCoreApplication.translate
        self.pattern = re.compile(
            r'QCoreApplication\.translate\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)'
        )
        
        self.pattern_tr = re.compile(
            r'\btr\(\s*"([^"]+)"\s*\)'
        )

        # Connessioni UI
        self.btnSelectPlugin.clicked.connect(self.select_plugin_folder)
        self.btnSelectI18n.clicked.connect(self.select_i18n_folder)
        self.btnGenerateTS.clicked.connect(self.generate_ts)
        self.btnGenerateQM.clicked.connect(self.generate_qm)
        self.btnClear.clicked.connect(self.clear_ui)
        self.btnClose.clicked.connect(self.close)
        self.btnSelectLrelease.clicked.connect(self.select_lrelease)
        self.btnOpenLinguist.clicked.connect(self.open_linguist)

    # ---------------------------------------------------------
    # Utility UI
    # ---------------------------------------------------------

    def log(self, msg):
        self.txtLog.append(msg)

    def clear_ui(self):
        self.txtPluginFolder.clear()
        self.txtI18nFolder.clear()
        self.txtLanguages.clear()
        self.txtPreview.clear()
        self.txtLog.clear()

    # ---------------------------------------------------------
    # Selezione cartelle
    # ---------------------------------------------------------

    def select_plugin_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            QCoreApplication.translate(
                "TranslationBuilderDialog", "Seleziona cartella plugin"
            )
        )
        if folder:
            self.txtPluginFolder.setText(folder)

    def select_i18n_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            QCoreApplication.translate(
                "TranslationBuilderDialog", "Seleziona cartella i18n"
            )
        )
        if folder:
            self.txtI18nFolder.setText(folder)

    def select_lrelease(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona lrelease.exe",
            "",
            "Eseguibili (*.exe)"
        )
        if path:
            self.txtLreleasePath.setText(path)
            QSettings().setValue("translation_builder/lrelease_path", path)

    # ---------------------------------------------------------
    # Scansione file .py
    # ---------------------------------------------------------

    def scan_files(self, root_folder):
        strings = []
        seen = set()

        for root, dirs, files in os.walk(root_folder):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    rel_path = os.path.relpath(path, root_folder)

                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            content = fh.read()
                    except Exception:
                        continue

                    # 1. QCoreApplication.translate(...)
                    for ctx, msg in self.pattern.findall(content):
                        key = (ctx, msg)
                        if key not in seen:
                            seen.add(key)
                            strings.append({
                                "context": ctx,
                                "source": msg,
                                "filename": rel_path.replace("\\", "/"),
                                "comment": None
                            })

                    # 2. tr("...")
                    for msg in self.pattern_tr.findall(content):
                        key = ("default", msg)  # oppure il nome del plugin
                        if key not in seen:
                            seen.add(key)
                            strings.append({
                                "context": "default",
                                "source": msg,
                                "filename": rel_path.replace("\\", "/"),
                                "comment": None
                            })

        return strings

    # ---------------------------------------------------------
    # Estrazione stringhe dai file .ui
    # ---------------------------------------------------------

    def scan_ui_strings(self, root_folder):
        ui_strings = []

        for root, dirs, files in os.walk(root_folder):
            for f in files:
                if f.endswith(".ui"):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, self.txtI18nFolder.text().strip())
                    rel_path = rel_path.replace("\\", "/")

                    ui_strings.extend(
                        self.extract_strings_from_ui(full_path, rel_path)
                    )

        return ui_strings

    def extract_strings_from_ui(self, full_path, rel_path):
        try:
            tree = safe_parse(full_path)
            root = tree.getroot()
        except Exception:
            return []

        class_el = root.find("class")
        context = class_el.text if class_el is not None else os.path.splitext(os.path.basename(full_path))[0]
        strings = []

        for string_el in root.findall(".//string"):
            text = string_el.text or ""
            text = text.strip()

            if not text:
                continue

            comment = string_el.get("comment")

            strings.append(
                {
                    "context": context,
                    "source": text,
                    "filename": rel_path,
                    "comment": comment
                }
            )

        return strings

    # ---------------------------------------------------------
    # Generazione TS
    # ---------------------------------------------------------

    def generate_ts(self):
        plugin_folder = self.txtPluginFolder.text().strip()
        i18n_folder = self.txtI18nFolder.text().strip()
        languages = [lang.strip() for lang in self.txtLanguages.text().split(",") if lang.strip()]

        if not os.path.isdir(plugin_folder):
            QMessageBox.warning(self, "Errore", "Cartella plugin non valida.")
            return

        if not os.path.isdir(i18n_folder):
            os.makedirs(i18n_folder)

        if not languages:
            QMessageBox.warning(self, "Errore", "Inserire almeno una lingua.")
            return

        self.log("Scansione in corso...")

        py_strings = self.scan_files(plugin_folder)
        ui_strings = self.scan_ui_strings(plugin_folder)
        seen = set((s["context"], s["source"]) for s in py_strings)
        merged = py_strings.copy()

        for item in ui_strings:
            key = (item["context"], item["source"])
            if key not in seen:
                merged.append(item)
                seen.add(key)

        all_strings = merged

        if not all_strings:
            self.log("Nessuna stringa trovata.")
            return

        self.txtPreview.clear()
        for item in all_strings:
            self.txtPreview.append(f"[{item['context']}] {item['source']}  ({item['filename']})")

        contexts = {}
        for item in all_strings:
            contexts.setdefault(item["context"], []).append(item)

        for lang in languages:
            plugin_name = os.path.basename(os.path.normpath(plugin_folder))
            ts_path = os.path.join(i18n_folder, f"{plugin_name}_{lang}.ts")

            self.log(f"Generazione: {ts_path}")
            ts = ET.Element("TS", version="2.1", language=f"{lang}_{lang.upper()}")

            for ctx, items in contexts.items():
                context_el = ET.SubElement(ts, "context")
                name_el = ET.SubElement(context_el, "name")
                name_el.text = ctx

                for item in items:
                    message_el = ET.SubElement(context_el, "message")
                    location_el = ET.SubElement(message_el, "location")
                    location_el.set("filename", item["filename"])
                    source_el = ET.SubElement(message_el, "source")
                    source_el.text = item["source"]

                    if item["comment"]:
                        comment_el = ET.SubElement(message_el, "translatorcomment")
                        comment_el.text = item["comment"]

                    ET.SubElement(message_el, "translation").text = ""

            tree = ET.ElementTree(ts)
            tree.write(ts_path, encoding="utf-8", xml_declaration=True)

        self.log("File TS generati con successo.")
        QMessageBox.information(self, "Completato", "File TS generati.")

    # ---------------------------------------------------------
    # Generazione QM (versione multipiattaforma + file TXT)
    # ---------------------------------------------------------

    def generate_qm(self):
        i18n_folder = self.txtI18nFolder.text().strip()

        if not os.path.isdir(i18n_folder):
            QMessageBox.warning(self, "Errore", "Cartella i18n non valida.")
            return

        ts_files = [f for f in os.listdir(i18n_folder) if f.endswith(".ts")]

        if not ts_files:
            QMessageBox.warning(self, "Errore", "Nessun file TS trovato.")
            return

        # -----------------------------------------------------
        # 1. Recupera il percorso di lrelease (TXT → QSettings → autodetect)
        # -----------------------------------------------------
        LRELEASE = self.get_lrelease_path()

        if not LRELEASE or not os.path.isfile(LRELEASE):
            QMessageBox.warning(
                self,
                "Errore",
                "Percorso di lrelease non valido.\n"
                "Selezionalo tramite il pulsante dedicato."
            )
            return

        # Salva sempre il percorso nel file TXT
        self.save_lrelease_path(LRELEASE)

        # -----------------------------------------------------
        # 2. Compilazione dei file .qm
        # -----------------------------------------------------
        for ts in ts_files:
            ts_path = os.path.abspath(os.path.join(i18n_folder, ts)).replace("\\", "/")
            qm_path = os.path.abspath(os.path.splitext(ts_path)[0] + ".qm").replace("\\", "/")
            self.log(f"Compilazione: {qm_path}")
            proc = QProcess()
            proc.setWorkingDirectory(i18n_folder)

            # Avvio multipiattaforma
            proc.start(LRELEASE, [ts_path, "-qm", qm_path])
            proc.waitForFinished()
            exit_code = proc.exitCode()
            stderr = bytes(proc.readAllStandardError()).decode("utf-8", errors="ignore")

            if exit_code != 0 or stderr.strip():
                self.log(f"ERRORE lrelease: {stderr}")
            else:
                if os.path.exists(qm_path):
                    self.log(f"Creato: {qm_path}")
                else:
                    self.log("ATTENZIONE: lrelease ha terminato senza errori, ma il file non è stato creato.")

        self.log("File QM generati.")
        QMessageBox.information(self, "Completato", "File QM generati.")

    
    def lrelease_config_file(self):
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(plugin_dir, "resources", "lrelease_path.txt")

    def load_lrelease_path(self):
        cfg = self.lrelease_config_file()
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass

        return ""

    def save_lrelease_path(self, path):
        cfg = self.lrelease_config_file()
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass

    def autodetect_lrelease(self):
        if os.name == "nt":
            candidates = [
                r"C:\Program Files\QGIS 4.0.0\apps\Qt5\bin\lrelease.exe",
                r"C:\Program Files\QGIS 4.0.0\6.6.0\mingw_64\bin\lrelease.exe",
                r"C:\OSGeo4W\bin\lrelease.exe"
            ]
        else:
            candidates = [
                "/Applications/QGIS.app/Contents/MacOS/bin/lrelease",
                "/usr/bin/lrelease",
                "/usr/local/bin/lrelease"
            ]

        for c in candidates:
            if os.path.isfile(c):
                return c

        from shutil import which
        found = which("lrelease")
        return found if found else ""

    def get_lrelease_path(self):
        txt = self.load_lrelease_path()
        if txt and os.path.isfile(txt):
            return txt

        settings = QSettings()
        qs = settings.value("translation_builder/lrelease_path", "")
        if qs and os.path.isfile(qs):
            return qs

        auto = self.autodetect_lrelease()
        if auto:
            return auto

        return ""

    def linguist_config_file(self):
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(plugin_dir, "resources", "linguist_path.txt")

    def load_linguist_path(self):
        cfg = self.linguist_config_file()
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass

        return ""

    def save_linguist_path(self, path):
        cfg = self.linguist_config_file()
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass

    def autodetect_linguist(self):
        if os.name == "nt":
            candidates = [
                r"C:\Program Files\QGIS 4.0.0\apps\Qt5\bin\linguist.exe",
                r"C:\Program Files\QGIS 4.0.0\6.6.0\mingw_64\bin\linguist.exe",
                r"C:\OSGeo4W\bin\linguist.exe"
            ]
        else:
            candidates = [
                "/Applications/QGIS.app/Contents/MacOS/bin/linguist",
                "/usr/bin/linguist",
                "/usr/local/bin/linguist"
            ]

        for c in candidates:
            if os.path.isfile(c):
                return c

        from shutil import which
        found = which("linguist")
        return found if found else ""

    def get_linguist_path(self):
        txt = self.load_linguist_path()
        if txt and os.path.isfile(txt):
            return txt

        auto = self.autodetect_linguist()
        if auto:
            return auto

        return ""

    def open_linguist(self):
        linguist = self.get_linguist_path()

        if not linguist or not os.path.isfile(linguist):
            QMessageBox.warning(
                self,
                "Qt Linguist non trovato",
                "Qt Linguist non è stato trovato automaticamente.\n"
                "Selezionalo manualmente."
            )
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Seleziona Qt Linguist",
                "",
                "Eseguibili (*)"
            )
            if not path:
                return
            linguist = path
            self.save_linguist_path(path)

        proc = QProcess()
        proc.startDetached(linguist)
