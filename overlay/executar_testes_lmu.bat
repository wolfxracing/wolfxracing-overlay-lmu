@echo off
call "%~dp0executar_todos_os_testes.bat" %*
set "WOLFX_TESTES_RC=%ERRORLEVEL%"
pause
exit /b %WOLFX_TESTES_RC%
