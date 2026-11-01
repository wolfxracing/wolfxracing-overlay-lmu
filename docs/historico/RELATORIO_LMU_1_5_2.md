# Relatório LMU 1.5.2 — correções do overlay LMU

Base: 1.5.1. Overlay do iRacing (homologado) **não foi alterado**.

## Resumo executivo
Os achados feitos no dash MagicDash4 LMU Sport (luz de ignição, energia virtual, farol, posição na classe) foram conferidos no overlay Python. Energia virtual e posição na classe já estavam corretas no overlay; foram corrigidos os itens abaixo.

## Alterações
| # | Item | Antes | Agora | Arquivo |
|---|------|-------|-------|---------|
| 1 | Motor parado (luz de ignição do painel) | Só "superaquecendo" gerava alerta | Alerta **MOTOR PARADO** (nível perigo) quando ignição = 1 e RPM < 100, na pista (não nos boxes). Partida (ignição 2) não conta | `ov_lmu.py`, `ov_alertas_lmu.py` |
| 2 | Janela Danos | MOTOR: ok / SUPERAQUECENDO | MOTOR: ok / SUPERAQUECENDO / **PARADO**; nova linha **FAROL** (ligado/apagado, `mHeadlights`); espaçamento ajustado | `ov_janelas_extra_lmu.py` |
| 3 | Desgaste de pneu | `mWear` = 0.0 exato virava "0% de vida" (log: `[0.0, 0.0, 0.932, 0.0]`) | 0.0 exato = sem leitura (None, exibido "--") | `ov_lmu.py` |
| 4 | Log | Linha "impacto LMU" repetida (1224 linhas) | No máximo 1 linha a cada 5 s | `overlay_lmu.py` |
| 5 | Versão | 1.5.1 | 1.5.2 | `overlay_lmu.py` |

## Já corretos (sem mudança)
- Energia virtual: `mVirtualEnergy` 0..1 (log 91,08%).
- Posição/gaps por classe: agrupamento do overlay por `mVehicleClass` (o erro "34 vs 12" era do dash, não do overlay).

## Testes
Novos casos em `testes/teste_lmu.py`: motor parado (ignição 1, RPM 0), partida não conta, ignição com RPM = funcionando, farol, `mWear` 0.0 = None, alerta na pista, sem alerta nos boxes.
**Não executados na nuvem** (sem PySide6/Windows). Sintaxe compilada OK em todos os arquivos alterados.

## Riscos / pendências
- "Motor parado" na largada com motor desligado antes da partida pode alertar brevemente (ignição 1, RPM 0, fora dos boxes). Avaliar no uso real.
- `mWear` 0.0 pode também ocorrer em pneu realmente no limite; hipótese a confirmar no jogo.
- Fonte de temperatura do pneu segue "interna" (aguarda confirmação com valores do jogo).

## Próximos passos
1. Rodar `executar_testes_lmu.bat` e enviar o resultado.
2. Abrir o LMU, apagar o motor/danificar e conferir alerta + janela Danos.
3. Backup dos originais: `backup_pre_1_5_2/`.
