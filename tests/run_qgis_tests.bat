@echo off
REM Run the QGIS-tier tests under the bundled QGIS Python (sets OSGeo4W env).
REM Adjust QGIS_ROOT if your install path differs.
set "QGIS_ROOT=C:\QGIS 3.44.10"
set "QT_QPA_PLATFORM=offscreen"
call "%QGIS_ROOT%\bin\python-qgis-ltr.bat" -m pytest -m qgis %*
