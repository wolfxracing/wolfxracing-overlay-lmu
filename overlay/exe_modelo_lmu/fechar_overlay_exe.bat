@echo off
rem Fecha o overlay do LMU (versao EXE) a forca. Nao mexe no Le Mans Ultimate nem em outros programas.
taskkill /IM WolfxRacing_LMU.exe /F >nul 2>nul
if errorlevel 1 (echo O overlay LMU nao estava em execucao.) else (echo Overlay LMU encerrado.)
timeout /t 2 >nul
