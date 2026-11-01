@echo off
cd /d "%~dp0"
echo Rodando os testes automaticos do overlay LMU (nao precisa do jogo)...
py -3.12 testes\teste_lmu.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_lmu_v12.py
if errorlevel 1 goto falhou
echo.
echo TODOS OS TESTES PASSARAM.
echo Lembrete: estes testes usam um jogo simulado. Eles NAO substituem a validacao com o Le Mans Ultimate de verdade.
goto fim
:falhou
echo.
echo ALGUM TESTE FALHOU - abra uma Issue no GitHub anexando esta tela.
:fim
pause
