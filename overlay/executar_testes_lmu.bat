@echo off
cd /d "%~dp0"
echo Rodando os testes automaticos do overlay LMU (nao precisa do jogo)...
py -3.12 testes\teste_lmu.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_lmu_v12.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_marcas.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v163.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_import.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_previas.py
py -3.12 testes\teste_v170_elementos.py
py -3.12 testes\teste_v170_central_real.py
py -3.12 testes\teste_v170_estados_vazios.py
py -3.12 testes\teste_v170_coach_ciclo_real.py
py -3.12 testes\teste_v170_coach_ciclo_lmu.py
py -3.12 testes\teste_v170_ritmo_ideal.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_coach_real.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_ritmo_voz.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_backup.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_amigos.py
if errorlevel 1 goto falhou
py -3.12 testes\teste_v170_ibt.py
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
