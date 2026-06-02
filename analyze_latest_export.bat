@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist "myenv\Scripts\python.exe" (
    echo ERROR: myenv was not found.
    echo Run install_bridge.bat first on a machine with dependency access.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Analyze latest export
    echo.
    echo Supported graphs/reports:
    echo   all        Produce every available graph/report
    echo.
    echo 1D graphs:
    echo   trace      Height versus timestamp or sample index
    echo   layers     Separate height trace per scan layer
    echo   histogram  Distribution of valid height readings
    echo.
    echo 2D graph:
    echo   heightmap  Top-down physical heightmap
    echo              X/Y axes with color and contour lines showing Z height
    echo.
    echo 3D graph:
    echo   surface3d  3D physical heightmap surface
    echo.
    echo Report:
    echo   summary    Text summary of samples, metadata, and stats
    echo.
    echo General flags:
    echo   all
    echo   trace layers histogram heightmap surface3d summary
    echo   --save
    echo   --title "Custom Plot Title"
    echo   --mark-invalid
    echo   --csv PATH_TO_EXPORT.csv
    echo   --export-dir exports
    echo   --output-dir analysis_outputs
    echo.
    echo 1D graph flags for trace, layers, histogram:
    echo   --layer LAYER_INDEX
    echo.
    echo 2D heightmap flags:
    echo   --tilt
    echo   --smooth NUMBER
    echo   --square
    echo   --contours COUNT
    echo   --heightmap-grid-x-count COUNT
    echo   --heightmap-grid-y-count COUNT
    echo   --cmap NAME
    echo.
    echo 3D surface flags:
    echo   --tilt
    echo   --smooth NUMBER
    echo   --square
    echo   --z-exaggeration NUMBER
    echo   --heightmap-grid-x-count COUNT
    echo   --heightmap-grid-y-count COUNT
    echo   --cmap NAME
    echo   --surface3d-max-grid COUNT
    echo.
    echo Summary report flags:
    echo   --layer LAYER_INDEX
    echo.
    echo Notes:
    echo   --layer applies to the 1D graphs/reports.
    echo   heightmap is the 2D X/Y plot with color/contours for Z height.
    echo   surface3d is the separate 3D surface plot.
    echo   heightmap and surface3d require SciPy.
    echo   Without --save, graphs open as interactive Matplotlib windows.
    echo   With --save, files are written to analysis_outputs.
    echo   Press Enter with no flags to use defaults.
    echo.
    echo Enter analysis flags.
    echo Examples:
    echo   heightmap --contours 20
    echo   trace heightmap summary --tilt --save
    echo   heightmap surface3d --title "Scan 12"
    echo   heightmap --tilt --square --smooth 0.1 --mark-invalid
    echo.
    set /p ANALYSIS_FLAGS=Flags: 
    "%~dp0myenv\Scripts\python.exe" -m src.analysis.run_latest_export !ANALYSIS_FLAGS!
) else (
    "%~dp0myenv\Scripts\python.exe" -m src.analysis.run_latest_export %*
)

echo.
echo Analysis complete.
pause
