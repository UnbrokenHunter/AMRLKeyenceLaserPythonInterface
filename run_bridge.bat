@echo off
setlocal

cd /d "%~dp0"

if not exist "myenv\Scripts\activate.bat" (
    echo Could not find myenv\Scripts\activate.bat.
    echo.
    echo Create the virtual environment first, or make sure this script is in the project root.
    echo Expected location: %CD%\myenv\Scripts\activate.bat
    echo.
    pause
    exit /b 1
)

call "myenv\Scripts\activate.bat"

python -m src.main
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Bridge exited with error code %EXIT_CODE%.
    echo.
    pause
)

exit /b %EXIT_CODE%
