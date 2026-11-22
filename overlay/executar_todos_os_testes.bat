@echo off
rem As dependencias de teste sao instaladas separadamente com requirements-teste.txt.
py -3.12 "%~dp0rodar_todos_os_testes.py" %*
exit /b %ERRORLEVEL%
