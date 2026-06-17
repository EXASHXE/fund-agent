@echo off
REM fund-agent-privacy-check.cmd - Windows wrapper for privacy audit
REM Requires Python 3.11+ on PATH

setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: python not found on PATH >&2
    exit /b 1
)

python "%REPO_ROOT%\scripts\privacy_audit.py" --repo-root "%REPO_ROOT%" %*
exit /b %errorlevel%
