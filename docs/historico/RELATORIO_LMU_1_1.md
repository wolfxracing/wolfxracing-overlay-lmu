# Overlay Le Mans Ultimate (LMU) — Versão 1.1 (classificação detalhada)

**Status: ENTREGUE PARA HOMOLOGAÇÃO. NÃO homologado.** Testado apenas com um jogo simulado (177 verificações automáticas, todas aprovadas). Nenhum número foi conferido contra o Le Mans Ultimate real.

## 1. Resumo executivo
- **Novidade 1.1:** a janela de classificação passou a ser **detalhada**, no padrão da referência enviada: posição na classe e variação desde o grid (▲/▼), número, marca, piloto, selos PIT/PEN/FIM/DNF/DSQ, paradas, combustível %, GAP, INT, melhor, última e média das últimas 5 voltas, com cabeçalho de sessão (tempo, volta, temperaturas).
- Versão do overlay para o LMU com as 6 janelas pedidas, no mesmo visual, tamanho e posição do overlay do iRacing: **classificação completa por classe, clima da pista, combustível com calculadora, telemetria, força G e delta**.
- Os arquivos do iRacing (`overlay_iracing.py`, `ov_nucleo.py`, `config.json`) **não foram alterados**. O LMU usa arquivos próprios (`config_lmu.json`, `overlay_log_lmu.txt`, etc.) e os dois overlays podem coexistir.
- Leitura **somente leitura** da memória compartilhada nativa do LMU (`LMU_Data`). Não exige plugin nem DLL; exige "Enable Plugins" ligado no jogo e vídeo em Borderless.

## 2. Análise objetiva
| Janela | Origem dos dados | Situação |
|---|---|---|
| Classificação detalhada | Do jogo: posição, classe, voltas, melhor/última, paradas, penalidades, combustível %, boxes, resultado, intervalo ao vizinho direto. Calculado pelo overlay: posição na classe, variação no grid (qualificação do jogo), média de 5 voltas, GAP/INT entre não vizinhos (marcado **"~"** = estimado) | Número/marca saem do nome do veículo ("#31"); significado de combustível %, GAP/INT e qualificação **a confirmar** |
| Clima | Temperaturas, chuva, umidade da pista, nuvens, vento | Escalas "pista molhada 1–7" e "céu" são do overlay; neblina e direção do vento **não existem** no LMU (mostram "--") |
| Combustível | Litros e capacidade do jogo; consumo/calculadora reaproveitados do iRacing | **Não considera Energia Virtual** (ver riscos) |
| Telemetria | Marcha, RPM, velocidade, pedais, volante, TC, ABS, balanço de freio | Sentido do volante e valores de TC/ABS/BB **a confirmar** |
| Força G | Aceleração do carro (eixos convertidos ao padrão do painel) | Sentido dos eixos **a confirmar** |
| Delta | Calculado pelo overlay (melhor volta limpa), como no iRacing | Delta do jogo só vai ao log para comparação (sinal não validado) |

Proteções: detecta jogo fechado, sem sessão, pausado e formato de memória diferente (jogo atualizado) — nesses casos não exibe dado errado; reconecta sozinho se o jogo for reaberto.

## 3. Riscos e dependências
1. **Energia Virtual (principal risco):** em categorias com limite de energia por stint, o jogo pode acabar a energia antes do combustível; a calculadora (só litros) ficará otimista. Mitigação: o valor da energia já é gravado no diagnóstico; incorporá-lo à calculadora é a próxima evolução recomendada.
2. **Estrutura de memória do jogo:** baseada na biblioteca MIT `pyLMUSharedMemory` (incluída, com licença). Atualização do jogo pode alterar o formato; o overlay entra em estado "incompatível" e avisa, sem mostrar dados.
3. **Sem homologação em sessão real:** convenções de sinal (força G, volante, delta), leitura de nome/número/classe e escalas de clima só se confirmam no jogo.
4. **Não existe no LMU (não inventado):** país do piloto, iRating/SOF, pneus e danos dos outros carros — essas colunas da referência não foram incluídas. A janela é mais larga que a do iRacing e precisa ser reposicionada na primeira abertura.
5. Fora do escopo desta versão: atalhos/Stream Deck, projeção de iRating, mapa, radar, pneus, setores, danos e demais janelas do iRacing.
6. Código GPL do TinyPedal **não foi copiado** (usado só como referência de leitura).

## 4. Recomendação final
Executar o `ROTEIRO_VALIDACAO_LMU.txt` (60–90 min, sessão offline com IA; o teste 2 foi ampliado para a classificação detalhada) e enviar `diagnostico_lmu.txt` e `overlay_log_lmu.txt`. Só considerar a versão homologada com os testes 2 a 9 anotados como PASSOU. Até lá, usar como apoio visual, não como base de decisão de estratégia.

## 5. Próximos passos
1. Rodar `executar_testes_lmu.bat` (deve terminar com "TODOS OS TESTES PASSARAM") e `testar_demo_lmu.bat`.
2. Com o jogo aberto e no carro: `diagnostico_lmu.bat` → enviar o `diagnostico_lmu.txt`.
3. Executar o roteiro e anotar PASSOU/FALHOU/DUVIDA.
4. Com base no resultado: corrigir divergências, incluir Energia Virtual na calculadora e, se desejado, atalhos/Stream Deck para o LMU.
5. Restrição de projeto mantida: a Fase 21 só avança após a homologação do iRacing.

## Arquivos entregues (pasta do overlay)
`overlay_lmu.py`, `ov_lmu.py`, `ov_classif_lmu.py`, `ov_janela_lmu.py`, `pyLMUSharedMemory/` (+ `License.txt`), `testes/teste_lmu.py`, `iniciar_overlay_lmu.bat`, `testar_demo_lmu.bat`, `diagnostico_lmu.bat`, `executar_testes_lmu.bat`, `fechar_overlay_lmu.bat`, `LEIA-ME_LMU.txt`, `ROTEIRO_VALIDACAO_LMU.txt`, `RELATORIO_LMU_1_0.md`, `previas_lmu/` (imagens das janelas com dados simulados).
