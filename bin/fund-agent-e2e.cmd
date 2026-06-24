@echo off
REM fund-agent-e2e.cmd - Windows wrapper for fund-agent-e2e
REM Delegates to the shared Python orchestrator: scripts/fund_agent_e2e.py
REM Requires Python 3.11+ on PATH

setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: python not found on PATH >&2
    exit /b 1
)

REM Forward all arguments to the shared Python E2E orchestrator
python "%REPO_ROOT%\scripts\fund_agent_e2e.py" %*
exit /b %errorlevel%
