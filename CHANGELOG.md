#Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog

and this project adheres to Semantic Versioning
.

##1.5 — Custom translation wrappers and optional offline automatic translation

##Release date: 2026-08-29

Added
Added support for custom translation wrappers:
tr("...")
self.tr("...")
_tr("...")
self._tr("...")
Added automatic detection of the translation context from the enclosing Python class.
Added fallback to the module/file name for module-level translation calls.
Added optional automatic translation using Argos Translate.
Added detection of the Argos Translate installation from the plugin.
Added detection of installed Argos language models.
Added optional installation of Argos language models from the plugin UI.
Added support for multiple target languages.
The first language specified is treated as the source language; all subsequent languages are treated as target languages.
Added support for language lists such as:
it, en
it, en, fr
it, en, fr, de, es
Added protection and restoration of common Qt placeholders during automatic translation, including %1, %2, %n, ${...} and {variable} patterns.
Added clearer Argos Translate status information to the UI.
Improved
TS files are now always created before automatic translation starts.
Automatic translation is no longer part of the critical TS-generation path.
The absence of Argos Translate does not prevent TS generation.
Missing Argos language models do not prevent TS generation.
Unsupported language pairs do not prevent TS generation.
Translation failures leave the affected messages as type="unfinished" instead of cancelling the operation.
Improved logging during Argos model installation and automatic translation.
Improved progress reporting for scanning, TS generation, automatic translation and QM compilation.
Heavy operations continue to run in a background QThread, keeping the QGIS interface responsive.
Improved handling of strings occurring in multiple Python and UI files.
Each occurrence of a string is tracked using separate <location> entries in the generated TS file.
Improved translation-context resolution for custom tr() and _tr() wrappers.
Changed
Replaced the previous HTTP-based automatic translation mechanism with Argos Translate.
Removed the dependency on deep-translator.
Automatic translation no longer requires a translation API or API key.
Automatic translation is performed locally using installed Argos language models.
Argos Translate is an optional dependency.
Argos language models are not bundled with the plugin and are installed only when requested by the user.
The plugin remains usable without Argos Translate.
Qt Linguist remains the recommended tool for reviewing and correcting machine-generated translations.
The plugin version remains 1.5. These changes are part of the 1.5 update and do not introduce a new version number.
Fixed
Fixed detection of custom _tr() wrapper methods.
Fixed cases where files were scanned successfully but strings were not extracted because only literal tr() calls were recognized.
Fixed translation context resolution for nested and class-based Python code.
Fixed duplicate translation entries for strings shared across multiple files.
Fixed .ui location paths so they are consistently relative to the plugin root.
Fixed the workflow where automatic translation failures could prevent users from obtaining the generated TS files.
Fixed the dependency on an external translation endpoint for automatic translation.
Improved handling of missing Argos models and unsupported source/target language pairs.

###Compatibility
QGIS 4.0+
Qt 6
Python 3.12+
Argos Translate: optional
Qt Linguist: optional
lrelease: required only for .qm compilation
Notes

Argos Translate is not required for the basic TranslationBuilder workflow.

The standard workflow is:

Select the QGIS plugin folder.
Select or create the i18n folder.
Enter the languages, for example it, en, fr.
Generate the .ts files.
Optionally install Argos Translate and the required language models.
Optionally perform automatic local translation.
Review and correct translations using Qt Linguist.
Compile the .ts files into .qm files using lrelease.

If Argos Translate or a required language model is unavailable, valid TS files are still generated and remain available for manual translation.

##1.4 — Real translation context and multi-file string tracking

##Release date: 2026-08-28

###Improved
tr("...") calls are no longer assigned to the generic "Default" context.
The scanner now walks the enclosing Python class and uses its name as the translation context.
Module-level translation calls fall back to the Python file name.
The scanner tracks every file in which a string occurs.
Shared strings across multiple .py and .ui files produce a single TS message with multiple <location> entries.
Fixed .ui file paths being calculated relative to the i18n folder instead of the plugin folder.

##1.3 — Add link to download lrelease

##Release date: 2026-04-14

###Added
Added a link to download lrelease.
Added support for multiple translation languages.

##1.2 — Removal of defusedxml and QGIS 4.0.1 Compatibility

##Release date: 2026-04-12

###Improvements
Removed the dependency on defusedxml.
Replaced XML parsing with xml.etree.ElementTree.
Improved compatibility with:
QGIS 4.0.1+
Qt6
Python 3.12
Updated plugin metadata and tags.
General code cleanup and stability improvements.

##1.1.0 — Translation detection improvements

##Release date: 2026-04-10

###Added
Added support for extracting strings marked with tr(), self.tr(), and QObject.tr().
Added secondary detection for translation calls beyond QCoreApplication.translate.
Added metadata flag hasTranslations=True for QGIS automatic translation loading.
Added improved handling of translation contexts for Python and UI files.
Added compatibility with QObject-based translation patterns.
Improved
Enhanced Python scanning for nested and multiline calls.
Improved UI responsiveness.
Improved cross-platform path normalization for Windows, macOS and Linux.
Fixed
Fixed missing detection of tr() strings in Python files.
Fixed duplicate context merging when scanning .ui files.
Fixed edge cases where .qm files were not generated despite successful lrelease execution.

##1.0.0 — Initial public release

##Release date: 2026-03-27

###Added
Initial public release of TranslationBuilder.
Extraction of translatable strings from Python files using QCoreApplication.translate.
Extraction of strings from .ui files via XML parsing.
Generation of .ts files for multiple languages.
Compilation of .qm files using lrelease.
Automatic detection of lrelease on Windows, macOS and Linux.
Manual selection of lrelease.
Integrated Qt Linguist launcher.
Preview panel for extracted strings.
Log panel for all operations.
Responsive UI compatible with QGIS 4 and Qt6.
Plugin metadata and GPL-3 license.
Fixed
Correct handling of duplicate strings across Python and UI files.
Improved path normalization for cross-platform compatibility.
Notes
Requires QGIS 4.0 or later.
Supports Qt6.
Depends on qpip==1.1.1.
Unreleased
Planned
Optional support for .qrc file scanning.
Automatic detection of Qt Linguist paths on additional Linux distributions.
Integration with QGIS Processing for batch translation workflows.
Additional improvements to Argos Translate model management.
Support for additional offline translation engines.