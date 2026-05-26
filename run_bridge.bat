@echo off
setlocal

cd /d "%~dp0"

if not exist "myenv\Scripts\python.exe" (
    echo Could not find myenv\Scripts\python.exe.
    echo.
    echo Create the virtual environment first by running install_bridge.bat.
    echo Expected location: %CD%\myenv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

"myenv\Scripts\python.exe" -c "import serial, textual" >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
    echo The virtual environment exists, but required packages are missing.
    echo.
    echo This run script does not install anything.
    echo Prepare the environment on a machine with the required packages available,
    echo or copy a known-good myenv folder to this computer.
    echo.
    pause
    exit /b 1
)

"myenv\Scripts\python.exe" -m src.main
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Bridge exited with error code %EXIT_CODE%.
    echo.
    pause
)

exit /b %EXIT_CODE%
