@echo off
title Instalador - Overlay LMU
where py >nul 2>nul
if errorlevel 1 goto sempython
echo [1/3] Preparando o Python 3.12 (versao compativel). Aguarde...
py install -y 3.12
py -3.12 --version >nul 2>nul
if errorlevel 1 goto semversao
echo [2/3] Atualizando o instalador de componentes...
py -3.12 -m pip install --upgrade pip
echo [3/3] Instalando os componentes do overlay (PySide6)...
py -3.12 -m pip install --only-binary=:all: PySide6-Essentials
if errorlevel 1 goto erro
echo.
echo Instalacao concluida. Agora use o arquivo testar_demo_lmu.bat para testar.
pause
exit /b 0
:sempython
echo Python nao encontrado. Instale o Python em python.org/downloads e execute este arquivo novamente.
pause
exit /b 1
:semversao
echo Nao foi possivel preparar o Python 3.12.
echo Abra o Prompt de Comando, digite:  py install 3.12  e depois execute este arquivo novamente.
pause
exit /b 1
:erro
echo Ocorreu um erro na instalacao. Tire um print desta tela e abra uma Issue no GitHub.
pause
exit /b 1
