predimrc_wrapper for Windows
============================

Pre-sizing of RC VTOL aircraft (quadplane) and multicopters.

Install
-------
1. Extract the whole zip into a folder.
2. Double-click install.bat. If Windows SmartScreen warns about an unknown publisher,
   choose "More info", then "Run anyway".

No administrator rights and no existing Python are needed. Internet access is needed during
the installation, which downloads Python and about 100 packages (about 1 GB once installed).
The application then starts in your browser. Afterwards, use the "PredimRC wrapper" shortcut
on the desktop. To stop the application, close its console window (or press Ctrl+C in
it): this also ends the Excel started for PredimRC. Closing the browser tab does not stop
it.

Quadplane aerodynamics: PredimRC and Excel
------------------------------------------
Multicopters work without them. The quadplane architecture needs:
- Microsoft Excel, which is not included;
- PredimRC, by Franck Aguerre, a separate program with its own terms of use (see
  THIRD_PARTY_NOTICES.md). When this package includes it (folder predimrc), the installer
  copies it into Documents\predimrc_wrapper\profiles, without replacing a workbook already
  there. Otherwise, get it from its author and copy it there, named PredimRC_<profile>.xls
  (for example PredimRC_SD7003.xls).

Where things are
----------------
Application:              %LOCALAPPDATA%\Programs\predimrc_wrapper
Studies and workbooks:    Documents\predimrc_wrapper
Settings and user data:   %USERPROFILE%\.predimrc_wrapper

Update: run install.bat from the new version, with the application closed.
Uninstall: run uninstall.bat in the application folder. Your studies are kept.

Licences: see LICENSE.txt, LICENSES and THIRD_PARTY_NOTICES.md.
