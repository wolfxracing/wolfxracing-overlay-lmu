# Mapa de comandos × ícones — Overlay LMU (Stream Deck XL)

Fonte dos comandos: tabela `ATALHOS_LMU` do `ov_atalhos_lmu.py` (24 atalhos: 20 da v1.4.0 + 4 da v1.3.0 do pacote). Nenhum comando foi inventado fora dela.
Chave de posição = **coluna,linha** (0,0 = canto superior esquerdo; XL: 0..7 × 0..3). Perfil: **Overlay LMU** (página principal + pasta Suporte).

Combinações **diferentes** das do iRacing (Ctrl+Alt+Shift / Ctrl+Alt): LMU usa **Ctrl+Shift+F13..F24** (janelas) e **Alt+Shift+F13..F20** (controles).

## 1. Janelas (16) — alternar mostrar/ocultar
| Pos. | Janela | Atalho | Ícone |
|---|---|---|---|
| 0,0 | Telemetria | Ctrl+Shift+F13 | janela_telemetria |
| 1,0 | Voltas | Ctrl+Shift+F14 | janela_voltas |
| 2,0 | Classificação | Ctrl+Shift+F15 | janela_classificacao |
| 3,0 | Clima | Ctrl+Shift+F16 | janela_clima |
| 4,0 | Combustível | Ctrl+Shift+F17 | janela_combustivel |
| 5,0 | Força G | Ctrl+Shift+F18 | janela_forca_g |
| 6,0 | Energia virtual | Ctrl+Shift+F19 | janela_energia |
| 7,0 | Pneus e freios | Ctrl+Shift+F20 | janela_pneus |
| 0,1 | Danos | Ctrl+Shift+F21 | janela_danos |
| 1,1 | Alertas | Ctrl+Shift+F22 | janela_alertas |
| 2,1 | Stints | Ctrl+Shift+F23 | janela_stints |
| 3,1 | Tendência | Ctrl+Shift+F24 | janela_tendencia |
| 3,3 | Luz ABS | Alt+Shift+F21 | janela_luz_abs |
| 4,3 | Luz TC | Alt+Shift+F22 | janela_luz_tc |
| 5,3 | Retorno à pista | Alt+Shift+F23 | janela_retorno |
| 6,3 | Estratégia de pneus | Alt+Shift+F24 | janela_estrategia |

## 2. Controles
| Pos. | Função | Atalho | Ícone |
|---|---|---|---|
| 4,1 | Classificacao: mostrar todas as classes (liga/desliga) | Alt+Shift+F17 | ctrl_classif_todas |
| 5,1 | Manter o overlay por cima do jogo (liga/desliga) | Alt+Shift+F18 | ctrl_manter_topo |
| 6,1 | Restaurar o tamanho das janelas (100%) | Alt+Shift+F19 | ctrl_restaurar_tamanhos |
| 7,1 | Zerar o pico de G | Alt+Shift+F16 | ctrl_zerar_pico_g |
| 0,2 | Modo economia de CPU (liga/desliga) | Alt+Shift+F13 | ctrl_economia_cpu |
| 1,2 | Aparecer sozinho ao entrar no carro (liga/desliga) | Alt+Shift+F14 | ctrl_aparecer_sozinho |
| 2,2 | Travar posicao das janelas (liga/desliga) | Alt+Shift+F15 | ctrl_travar_posicao |
| 1,3 | FECHAR o overlay (o mesmo que Sair no menu da bandeja) | Alt+Shift+F20 | ctrl_fechar |

## 3. Ações que abrem arquivos do Windows (sem atalho)
| Pos. | Função | Ícone |
|---|---|---|
| 0,3 | Iniciar overlay (`iniciar_overlay_lmu.bat`) | ctrl_iniciar |
| 2,3 | Forçar fechamento (`fechar_overlay_lmu.bat`) | ctrl_forcar_fechamento |
| 5,2 | Modo demo (`testar_demo_lmu.bat`) | sup_demo |
| 6,2 | Abrir log (`overlay_log_lmu.txt`) | sup_log |
| 7,2 | Pasta do overlay LMU | sup_pasta_overlay |
| 7,3 | Pasta "Suporte" (abre a subpágina) | sup_pasta_suporte |

## 3b. Botões decorativos (sem ação)
| Pos. | Ícone |
|---|---|
Implementados como ação "Hotkey" sem nenhuma tecla configurada: não enviam nada.

## 4. Pasta Suporte (tecla 0,0 = Voltar)
Lista de atalhos (`ATALHOS_STREAM_DECK_LMU.txt`), Guia rápido (`LEIA-ME_LMU.txt`), Roteiro de validação, Rodar testes, Rodar diagnóstico (`diagnostico_lmu.bat`), Ver diagnóstico (`diagnostico_lmu.txt`).

## 5. Diferenças em relação ao perfil do iRacing
- Sem botões de perfil Treino/Classificação/Corrida: o overlay LMU não tem esse recurso.
- Sem Relativo, Mapa, Radar, Setores, Limpar impactos: não existem no LMU. Em troca: Energia, Pneus e freios, Alertas, Stints, Tendência e "Todas as classes".
- Limite técnico igual ao do iRacing: o Stream Deck não lê o estado do overlay; o botão alterna, mas o ícone não muda sozinho (variantes "desligada" ficam em `icones/variantes_desligado` para uso manual).

## 6. Padrão visual
Idêntico ao do iRacing: fibra de carbono grafite, âmbar (padrão), vermelho (perigo/fechar), verde (iniciar/ligado), roxo, cinza; rótulo em caixa alta itálico com sombra; olho no canto das janelas; 144×144 px. Desenhos originais.
