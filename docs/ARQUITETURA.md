# Arquitetura (para quem vai contribuir)

## Visão geral

- **Overlay**: Python 3.12 + PySide6. Janelas transparentes e sempre no topo, desenhadas com `QPainter` (sem imagens por janela). Tudo local.
- **Fluxo**: `iniciar_overlay_lmu.bat` → `pyw -3.12 overlay_lmu.py` → leitura da memória compartilhada (`pyLMUSharedMemory`) → `ov_lmu.*` transforma em dicionários → janelas (`base.JanelaBase`) recebem `atualizar(dados)` e repintam numa taxa própria.
- **Visual**: camada central em `overlay_iracing.py` (`TEMA`, `fonte()`, `fonte_titulo()`, `pintar_superficie()`): temas *clássico*, *moderno*, *Sport* e *Glass Fumê* (`TEMA["vidro"]`, `_superficie_vidro()`). Mudar a aparência de todas as janelas = mexer aí.
- **Dash**: scripts em `dash/tools` geram o `.simhubdash` (JSON do Dash Studio + imagens + JavaScript).
- **Stream Deck**: scripts em `streamdeck/gerador` geram ícones e perfil a partir da tabela de atalhos.

## Arquivos do overlay

| Arquivo | Papel |
|---|---|
| `overlay_lmu.py` | Programa principal do LMU: leitura da memória compartilhada, montagem dos dados e das janelas, bandeja, atalhos |
| `ov_lmu.py` | Camada de dados do LMU, **sem Qt**: pneus, danos (motor parado, farol), energia virtual, bandeiras, jogador, classes |
| `ov_classif_lmu.py` | Agrupamento por classe, GAP/INT, médias |
| `ov_estrategia_lmu.py` | Energia, stints e tendência de ritmo |
| `ov_alertas_lmu.py` | Regras dos alertas na pista (lógica pura) |
| `ov_janela_lmu.py`, `ov_janelas_extra_lmu.py` | Janelas específicas do LMU (classificação, clima, energia, pneus, danos, alertas, stints, tendência) |
| `ov_atalhos_lmu.py` | Tabela de atalhos globais do LMU |
| `ov_demo_lmu.py` | Dados simulados para `--demo` |
| `overlay_iracing.py`, `ov_nucleo.py` | **Base compartilhada** com o overlay de iRacing (janelas, tema, config, bandeja). Cópia embutida: este repositório é independente |
| `pyLMUSharedMemory/` | Leitor da memória compartilhada do LMU (MIT, Tony Whitley e Xiang) |
| `ov_v12.py` | Lógica pura da 1.2.0 (sem Qt): Retorno à pista, Estratégia de pneus, histórico do gráfico de pedais (compartilhada com o overlay do iRacing) |
| `testes/teste_lmu.py`, `testes/teste_lmu_v12.py` | Testes automáticos (jogo simulado) |

## Princípios do projeto

1. **Nada é inventado.** Dado ausente vira `None`/`--`; valor calculado/estimado é marcado com `~`.
2. **Lógica pura separada da interface** sempre que possível (testável sem Qt).
3. **Sem injeção de código** no jogo; só telemetria oficial (SDK / memória compartilhada).
4. **Sem marcas registradas** no repositório (logos de jogos e de fabricantes).
5. **Sem dados pessoais** em arquivos versionados (config, logs, recordes, mapas).

## Testes

`overlay\executar_testes_lmu.bat` (ou `py -3.12 overlay/testes/teste_lmu.py`). Usa um jogo simulado em memória (não precisa do LMU).

Para renderizar as janelas fora do Windows (CI ou prévias), defina `QT_QPA_PLATFORM=offscreen`. As fontes do Windows (Bahnschrift) não existem em outros sistemas; o layout cai numa fonte substituta.

## Ideias de contribuição

- Calibração real da temperatura dos pneus (e testes com mais carros).
- Novos idiomas (hoje os textos estão em pt-BR).
- Layouts do dash para outras telas e resoluções.
- Testes com mais carros/classes e relatórios de validação no jogo real.
