@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\prepare_office.py
  goto finished
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\prepare_office.py
  goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 scripts\prepare_office.py
  goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
  python scripts\prepare_office.py
  goto finished
)
echo No se encontro Python. Abra este proyecto en Codex y pida ejecutar scripts/prepare_office.py con su interprete Python 3.10 o posterior.
exit /b 1
:finished
set "CHB_PREP_RESULT=%errorlevel%"
if not "%CHB_PREP_RESULT%"=="0" echo La preparacion no termino. Revise el resultado anterior con Codex.
echo La conexion remota no se activa desde este archivo. Consulte docs\REUNION_CASA_OFICINA.md.
pause
exit /b %CHB_PREP_RESULT%
