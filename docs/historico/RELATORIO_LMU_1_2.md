# Overlay Le Mans Ultimate (LMU) — Versão 1.2 (janelas novas de estratégia)

**Status: ENTREGUE PARA HOMOLOGAÇÃO. NÃO homologado.** Testado apenas com um jogo simulado (336 verificações automáticas, todas aprovadas). Nenhum número foi conferido contra o Le Mans Ultimate real.

## 1. Resumo executivo
- **Novidade 1.2:** seis janelas que só existem no LMU, a partir das ideias das telas do BlackRack que você enviou (usadas apenas como referência de conceito/visual; nenhum código de terceiros foi copiado):
  1. **Energia + combustível** — energia virtual e litros lado a lado, recurso que limita, alcance, situação ("chega ao fim" / "1 parada, entre as voltas A e B" / "~N paradas"), alvo por volta.
  2. **Pneus e freios** — temperatura, pressão, vida, composto e freio das 4 rodas, óleo e água.
  3. **Danos** — 8 zonas de impacto, peças soltas, rodas furadas, superaquecimento, último impacto.
  4. **Alertas na pista** — FCY/amarela/vermelha, azul, classe mais rápida atrás, carro lento/parado à frente, saída dos boxes, limitador e limite dos boxes, parada solicitada, penalidade, reserva.
  5. **Histórico de stints** — por stint: voltas, tempo, energia, combustível, pneu, desgaste, ritmo e diferença para a melhor volta.
  6. **Tendência de ritmo** — gráfico das voltas limpas, reta de tendência (s/volta), ritmo das últimas 5 e temperatura da pista.
- O overlay passa a ter **12 janelas** no LMU. Todas ligam/desligam pelo ícone da bandeja e guardam posição e tamanho.
- **Pastas separadas (pedido do autor, risco zero para o iRacing):** o LMU agora vive em `Documents\overlay_iracing\overlay_lmu`, ao lado da pasta do iRacing (`...\overlay_iracing\overlay_iracing`). Todos os arquivos do LMU foram removidos da pasta do iRacing (só os que eu criei, conferidos antes). A pasta do LMU leva uma **cópia idêntica** de `overlay_iracing.py`, `ov_nucleo.py` e `config.json` (reaproveitados pelo desenho das janelas). Os arquivos do iRacing seguem **idênticos** (conferido por hash antes e depois).
- **Fora desta entrega, por sua escolha:** o layout do Stream Deck XL para o LMU (próxima etapa).

## 2. Análise objetiva
| Janela | Medido pelo jogo | Calculado pelo overlay (marcado "~") | Ponto a confirmar no jogo real |
|---|---|---|---|
| Energia + combustível | Energia virtual (fração 0–1), litros, capacidade | Consumo por volta (média das voltas limpas), alcance, limitante, janela de pit, alvo por volta | Semântica da energia virtual; se energia e combustível são reabastecidos juntos |
| Pneus e freios | Temperatura (3 pontos), pressão, desgaste, composto, freio, óleo, água, furado/solto | Média da temperatura; faixa ideal = ótima do jogo ±10 °C (regra do overlay) | **Sentido do desgaste** (suposto 100 % = novo); ordem das rodas |
| Danos | 8 zonas (0–2), peça solta, superaquecimento, furado, último impacto | — | **Ordem das 8 zonas** (suposta: frente e sentido horário) |
| Alertas | Fase da sessão (FCY/parada), amarela por setor, bandeira azul, boxes, penalidades, limitador, velocidade dos carros | Distância/tempo até o contato, classe mais rápida atrás, carro lento à frente, limite dos boxes (medido pela velocidade com limitador ligado) | Numeração dos setores da amarela local; limiares (600 m / 350 m / 70 km/h / 900 m) são definição do overlay |
| Stints | Níveis, composto, desgaste, voltas e tempos | Totais por stint, ritmo (voltas limpas) | Se o stint "parcial" (overlay aberto no meio) aparece como esperado |
| Tendência | Tempos de volta, temperatura da pista | Regressão linear (≥ 4 voltas limpas), ritmo das últimas 5 | Critério de volta limpa (≤ 130 % da melhor, sem boxes) |

Regras de projeto mantidas: nada estimado é apresentado como medido; o que o LMU **não informa** (% de dano, tempo de reparo, previsão do tempo, tempo de parada planejado, pneus/dano de outros carros) **não foi incluído**.

Cobertura de testes automáticos novos: leitores de dados (pneus, danos, energia, bandeiras), painel de energia (alcance, limitante, paradas, janela), stints e tendência (parada, volta lenta, volta de saída, sessão nova, parcial), alertas (cada tipo, limiares, limite dos boxes, ordenação, limite de 6), caminho completo pela memória simulada, configuração (tipos inválidos, perfis), desenho das 6 janelas (com dados, demo, sem dados e extremos) e diagnóstico.

## 3. Riscos e dependências
1. **Sem homologação em sessão real** — os dois pontos mais sensíveis são o **sentido do desgaste do pneu** e a **ordem das zonas de dano**; ambos são ajustáveis em uma linha de `ov_lmu.py` depois do teste (testes 11 e 12 do roteiro).
2. **Alertas são ajuda visual**, não regra de prova: os limiares são do overlay e podem gerar aviso falso ou deixar de avisar; não substituem retrovisor, rádio nem bandeiras do jogo.
3. **Limite dos boxes** só é conhecido depois da primeira passagem com o limitador (medido; o jogo não informa o valor).
4. **Calculadora de litros herdada do iRacing** (janelas Voltas e Combustível) continua só em litros; em prova limitada por energia, usar a janela Energia.
5. **Espaço na tela:** 12 janelas. As posições iniciais das novas são sugestões; é preciso posicionar e desligar as que não forem usadas.
6. Estrutura de memória do jogo: biblioteca MIT `pyLMUSharedMemory`; atualização do jogo pode alterar o formato (o overlay detecta e não mostra dado errado).
7. Código GPL do TinyPedal e código do BlackRack **não foram copiados**.

## 4. Recomendação final
Executar o `ROTEIRO_VALIDACAO_LMU.txt` atualizado: testes 1–9 (janelas base) e **10–14 (janelas novas)**, em sessão offline com IA (cerca de 2 a 3 horas, em mais de uma sessão), e enviar `diagnostico_lmu.txt` e `overlay_log_lmu.txt`. O diagnóstico agora imprime os valores crus de desgaste, temperaturas, zonas de dano, bandeiras e boxes; o log registra impactos, mudanças de bandeira e consumo de energia, o que permite corrigir sentido/ordem sem nova rodada. Até a homologação, usar as janelas novas como apoio visual, não como base de decisão de estratégia.

## 5. Próximos passos
1. Rodar `executar_testes_lmu.bat` ("TODOS OS TESTES PASSARAM") e `testar_demo_lmu.bat` (as 6 janelas novas aparecem com dados simulados).
2. Com o jogo aberto e no carro: `diagnostico_lmu.bat` → enviar o `diagnostico_lmu.txt`.
3. Executar os testes 10 a 14 e anotar PASSOU / FALHOU / DUVIDA.
4. Com o resultado: corrigir divergências (desgaste, zonas, setores da amarela, limiares).
5. **Próxima etapa já combinada:** layout do Stream Deck XL para o LMU (reaproveitando o gerador de perfil do iRacing, com atalhos que não colidam).
6. Restrição de projeto mantida: a Fase 21 só avança após a homologação do iRacing.

## Arquivos entregues (pasta `overlay_lmu`) — novos/alterados na 1.2
Novos: `ov_estrategia_lmu.py`, `ov_alertas_lmu.py`, `ov_janelas_extra_lmu.py`, `ov_demo_lmu.py`, `RELATORIO_LMU_1_2.md`.
Alterados: `overlay_lmu.py` (versão 1.2, 12 janelas, config, diagnóstico), `ov_lmu.py` (leitores de pneus/danos/energia/bandeiras), `testes/teste_lmu.py` (336 verificações), `LEIA-ME_LMU.txt`, `ROTEIRO_VALIDACAO_LMU.txt`, `previas_lmu/`.
Inalterados (pasta do iRacing): `overlay_iracing.py`, `ov_nucleo.py`, `config.json`. Na pasta `overlay_lmu` há cópias idênticas deles.
