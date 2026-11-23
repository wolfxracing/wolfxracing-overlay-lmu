@echo off
rem Atualiza a pasta do overlay LMU para a build deste pacote (pacote COMPLETO: serve a partir de qualquer build anterior).
rem Uso: ATUALIZAR_LMU.bat "C:\caminho\da\pasta_overlay_lmu"        (acrescente --simular para so ver o que seria feito)
cd /d "%~dp0"
if "%~1"=="" (echo Informe a pasta do overlay LMU: ATUALIZAR_LMU.bat "C:\caminho\da\pasta"& exit /b 2)
py -3.12 atualizar_lmu.py %*
exit /b %errorlevel%
