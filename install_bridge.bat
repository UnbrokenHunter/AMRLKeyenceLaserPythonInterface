@echo off
setlocal

cd /d "%~dp0"

echo Installing AMRL Keyence / SpiiPlusSPC Bridge Interface
echo Project folder: %CD%
echo.

if not exist "requirements.txt" (
    echo Could not find requirements.txt.
    echo Make sure this script is in the project root.
    echo.
    pause
    exit /b 1
)

where py >nul 2>nul
if "%ERRORLEVEL%"=="0" (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if "%ERRORLEVEL%"=="0" (
        set "PYTHON_CMD=python"
    ) else (
        echo Could not find Python.
        echo Install Python, then run this script again.
        echo.
        pause
        exit /b 1
    )
)

if not exist "myenv\Scripts\activate.bat" (
    echo Creating virtual environment: myenv
    %PYTHON_CMD% -m venv myenv
    if not "%ERRORLEVEL%"=="0" (
        echo.
        echo Failed to create virtual environment.
        echo.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists: myenv
)

call "myenv\Scripts\activate.bat"
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo Failed to upgrade pip.
    echo.
    pause
    exit /b 1
)

echo.
echo Installing requirements...
python -m pip install -r requirements.txt
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo Failed to install requirements.
    echo.
    pause
    exit /b 1
)

echo.
echo Installation complete.
echo You can now run run_bridge.bat.
echo.
pause
exit /b 0
