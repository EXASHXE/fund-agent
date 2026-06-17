@echo off
REM fund-agent-e2e.cmd - Windows wrapper for fund-agent-e2e
REM Requires Python 3.11+ on PATH

setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: python not found on PATH >&2
    exit /b 1
)

REM Forward all arguments to the bash script via python invocation
python -m fund_agent.cli analyze-portfolio %*
exit /b %errorlevel%
