@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3 was not found. Install Python 3 and try again.
    pause
    exit /b 1
)

python -c "import tkinter; print('Runtime dependencies: OK')"
if errorlevel 1 (
    echo ERROR: Python Tkinter is missing. Install Python with Tcl/Tk support.
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing build dependencies...
    python -m pip install -r requirements-build.txt
    if errorlevel 1 (
        echo ERROR: Could not install PyInstaller. Check your internet connection.
        pause
        exit /b 1
    )
)

python -m PyInstaller --noconfirm --clean --windowed --onefile --name MyMusic --workpath "build\pyinstaller" --distpath "dist" --specpath "build" --hidden-import webview.platforms.edgechromium --hidden-import webview.platforms.winforms app.pyw
if errorlevel 1 (
    echo ERROR: EXE build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\MyMusic.exe
pause
