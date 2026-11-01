# Overlay LMU 1.5.0 - correcao das temperaturas (pneu e freio)

**Status: corrigido, aguardando conferencia no jogo.** Alteracoes so na pasta overlay_lmu (iRacing intocado).
Backup dos arquivos anteriores em `backup_pre_1_5/`.

## Causas
1. **Freio:** o jogo informa `mBrakeTemp` em **Kelvin** (parado nos boxes o valor e 290-295 = temperatura ambiente).
   O overlay tratava como Celsius e mostrava ~273 C a mais.
2. **Pneu:** o overlay usava so a temperatura de **superficie** (`mTemperature`). O MFD do jogo mostra um valor
   "entre a superficie e a camada interna" (FAQ do TinyPedal), portanto o overlay ficava mais frio e oscilante.

## O que mudou (`ov_lmu.py`)
- `FREIO_EM_KELVIN = True` -> freio = bruto - 273,15.
- `TEMP_PNEU_FONTE = "meio"` -> media de superficie e camada interna. Alternativas: "superficie", "interna", "carcaca".
- Log (a cada 60 s) passa a gravar superficie, camada interna, carcaca e freio bruto, para conferir com o jogo.
- Diagnostico mostra os mesmos valores crus. Rodape da janela atualizado. Teste do freio ajustado.

## Conferencia
Comparar a janela Pneus e freios com o MFD do jogo. Se o pneu ainda divergir, enviar `overlay_log_lmu.txt`
com o valor do jogo anotado: troca-se `TEMP_PNEU_FONTE` em uma linha.
