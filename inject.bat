@echo off
rem ---------------------------------------------------------------------------
rem  inject.bat  -  ORIGINAL (read-only) + ASSETS -> SC3E
rem  Copies the original game to SC3E and re-encodes every asset you edited in ASSETS
rem  (text, EXE strings, fonts, pictures, voices). Unchanged assets stay byte-identical.
rem  Usage: inject.bat [text,exe,fonts,pics,voices]   (optional: only run these steps on the existing SC3E)
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3 was not found in PATH. & exit /b 1)
python -c "import PIL" >nul 2>nul || (echo Installing Pillow... & python -m pip install pillow numpy)
if not exist ASSETS\manifest.json (echo ASSETS not found - run extract.bat first. & exit /b 1)

if "%~1"=="" (
    python tools\build.py || goto :fail
) else (
    python tools\build.py --no-copy --only %~1 || goto :fail
)
echo.
echo Done. Run the game from SC3E (e.g. DOSBox: mount c "%~dp0SC3E" ^& c: ^& sc3.exe)
exit /b 0

:fail
echo.
echo *** build FAILED ***
exit /b 1
