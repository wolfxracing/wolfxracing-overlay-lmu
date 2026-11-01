@echo off
cd /d "%~dp0"
echo Diagnostico do overlay LMU.
echo Abra o Le Mans Ultimate, entre numa sessao (pode ser offline), sente no carro e so entao tecle algo aqui.
pause
py -3.12 overlay_lmu.py --diagnostico
echo.
echo O resultado foi gravado em diagnostico_lmu.txt - abra uma Issue no GitHub anexando esse arquivo.
pause
