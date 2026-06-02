@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist "myenv\Scripts\python.exe" (
    echo ERROR: myenv was not found.
    echo Run install_bridge.bat first on a machine with dependency access.
    pause
    exit /b 1
)

if not "%~1"=="" (
    "%~dp0myenv\Scripts\python.exe" -m src.analysis.run_latest_export %*
    set "ANALYSIS_EXIT=!ERRORLEVEL!"
    echo.
    echo Analysis complete.
    pause
    exit /b !ANALYSIS_EXIT!
)

:interactive
call :print_help
echo.
set "ANALYSIS_FLAGS="
set /p ANALYSIS_FLAGS=Flags ^(q to quit^): 

if /I "!ANALYSIS_FLAGS!"=="q" goto done
if /I "!ANALYSIS_FLAGS!"=="quit" goto done
if /I "!ANALYSIS_FLAGS!"=="exit" goto done

echo.
"%~dp0myenv\Scripts\python.exe" -m src.analysis.run_latest_export !ANALYSIS_FLAGS!
echo.
echo Analysis complete. Close any Matplotlib windows, then enter new flags to rerun.
echo.
goto interactive

:done
echo.
echo Exiting analysis launcher.
exit /b 0

:print_help
echo Analyze latest export
echo.
echo Graphs and reports:
echo   all                       Produce every graph and report
echo   trace                     Height versus time or sample index
echo   layers                    One height trace per scan layer
echo   histogram                 Distribution of valid height readings
echo   heightmap                 2D X/Y map; color and contours show Z height
echo   surface3d                 3D physical heightmap surface
echo   summary                   Text summary of samples, metadata, and stats
echo.
echo General flags:
echo   --save                    Save files to analysis_outputs instead of only opening windows
echo   --title TEXT              Custom plot/report title
echo   -inv, --mark-invalid      Mark invalid samples on supported graphs
echo   --csv PATH                Analyze an explicit CSV file
echo   --export-dir PATH         Folder containing CSV exports
echo   --output-dir PATH         Folder for saved analysis outputs
echo   --layer INDEX             Restrict 1D graphs and summary to one layer
echo.
echo Heightmap and surface flags:
echo   -t,  --tilt               Subtract a best-fit tilt plane before plotting
echo   -s,  --smooth NUMBER      Gaussian smoothing sigma; 0 disables smoothing
echo   -sq, --square             Fill metadata X/Y extents with an interpolated grid
echo   -l,  --contours COUNT     Number of contour lines; 0 disables them
echo   -z,  --z-exaggeration N   Multiply displayed Z values for surface3d
echo        --cmap NAME          Matplotlib colormap, such as turbo or viridis
echo        --heightmap-grid-x-count COUNT
echo        --heightmap-grid-y-count COUNT
echo        --surface3d-max-grid COUNT
echo.
echo Examples:
echo   heightmap -l 20
echo   heightmap -t -sq -s 0.1 -inv
echo   trace heightmap summary -t --save
echo   heightmap surface3d -z 20 --title "Scan 12"
echo.
echo Press Enter with no flags to use defaults.
exit /b 0
