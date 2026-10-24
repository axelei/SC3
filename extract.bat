@echo off
rem ---------------------------------------------------------------------------
rem  extract.bat  -  ORIGINAL (read-only) -> ASSETS
rem  Extracts all texts, fonts, pictures (PNG) and voices (WAV) of the game.
rem  WARNING: overwrites ASSETS. Edited files in ASSETS are lost unless you answer N.
rem  Usage: extract.bat [/y]      (/y = do not ask for confirmation)
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3 was not found in PATH. & exit /b 1)
python -c "import PIL" >nul 2>nul || (echo Installing Pillow... & python -m pip install pillow numpy)

if exist ASSETS\manifest.json if /i not "%~1"=="/y" (
    echo ASSETS already exists. Re-extracting will OVERWRITE every file in it, including your translations.
    choice /c YN /m "Continue"
    if errorlevel 2 exit /b 0
)

echo.
echo === [1/4] texts and fonts ===
python tools\extract.py text fonts || goto :fail
echo.
echo === [2/4] pictures (PNG, takes a few minutes) ===
python tools\extract.py pics || goto :fail
echo.
echo === [3/4] voices (WAV, takes a few minutes, ~740 MB) ===
python tools\extract.py voices || goto :fail
echo.
echo === [4/4] palette swatches ===
python tools\setpal.py swatches || goto :fail
echo.
echo Done. Edit the files in ASSETS and then run inject.bat
exit /b 0

:fail
echo.
echo *** extraction FAILED ***
exit /b 1
