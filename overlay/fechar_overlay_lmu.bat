@echo off
rem Fecha o overlay do LMU a forca (use se ele travar).
rem Encerra SOMENTE processos cujo comando contem overlay_lmu.py; nao mexe no Le Mans Ultimate, no overlay do iRacing nem em outros Python.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$n=0; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overlay_lmu.py*' -and $_.Name -match '^(pythonw?|pyw?)\.exe$' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $n++ }; if ($n -gt 0) { Write-Host 'Overlay LMU encerrado.' } else { Write-Host 'O overlay LMU nao estava em execucao.' }"
timeout /t 2 >nul
