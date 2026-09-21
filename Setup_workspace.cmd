@echo off
setlocal
rem pushd gives UNC checkouts a temporary drive mapping for this invocation.
pushd "%~dp0"
if errorlevel 1 goto location_error

if exist ".venv\Scripts\python.exe" goto try_venv
goto try_python

:try_venv
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto venv

:try_python
where python >nul 2>&1
if errorlevel 1 goto try_py
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto python

:try_py
where py >nul 2>&1
if errorlevel 1 goto python_missing
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto python_missing
goto py

:venv
".venv\Scripts\python.exe" -B workspace_setup.py %*
set "setup_exit=%errorlevel%"
goto done

:python
python -B workspace_setup.py %*
set "setup_exit=%errorlevel%"
goto done

:py
py -3 -B workspace_setup.py %*
set "setup_exit=%errorlevel%"
goto done

:python_missing
echo Python 3.11 or newer was not found. Install Python, then run this file again.
set "setup_exit=1"
goto done

:location_error
echo Cannot open the workspace directory: %~dp0
if not defined SRD46_SETUP_NO_PAUSE pause
exit /b 1

:done
echo.
if not "%setup_exit%"=="0" echo Setup failed. Read the error above before retrying.
popd
if not defined SRD46_SETUP_NO_PAUSE pause
exit /b %setup_exit%
