@echo off
cd /d "%~dp0"
if not exist emblemas\novos mkdir emblemas\novos
echo Coloque as imagens (PNG, JPG, WEBP ou SVG) na pasta emblemas\novos. O nome do arquivo e a marca, ex.: toyota.svg, aston-martin.png
echo.
py -3.12 preparar_emblemas.py
echo.
start "" "%~dp0emblemas"
pause
