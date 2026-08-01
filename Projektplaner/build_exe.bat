@echo off
echo ============================================
echo   Projektplaner - Build zu .exe
echo ============================================
echo.
echo Installiere benoetigte Pakete...
pip install -r requirements.txt

echo.
echo Baue die .exe (das kann 1-2 Minuten dauern)...
python -m PyInstaller --onefile --windowed --name Projektplaner app.py

echo.
echo ============================================
echo   Fertig! Die fertige App liegt hier:
echo   dist\Projektplaner.exe
echo ============================================
pause