# Overlay Le Mans Ultimate (LMU) — Versão 1.3.3 (correções dos primeiros testes no jogo real)

**Status: PARCIALMENTE VALIDADO.** Primeira sessão real (30/10/2026) com a v1.2: leitura do jogo, energia virtual, pneus, delta e gaps funcionaram. Três pontos falharam e foram corrigidos na 1.3 (366 verificações automáticas, 0 falhas). As correções **ainda não foram conferidas no jogo**.

## 1. Resumo executivo
| Problema relatado | Causa encontrada | Correção 1.3 | Confiança |
|---|---|---|---|
| Bati na lateral esquerda e o amostrador de danos acusou a direita | Ordem das 8 zonas suposta no sentido horário; o jogo usa o **anti-horário** a partir da frente. Log real: impacto em x=+1,04 m (esquerda), z=−1,72 m (frente) acendeu o índice 1 | Ordem corrigida (frente → frente-esquerda → esquerda …) e desenho espelhado; nova linha "LADO DO ÚLTIMO IMPACTO" calculada pela posição medida pelo jogo | Média-alta (1 batida real + posição); falta conferir direita, traseira e quinas |
| Direção e velocidade do vento não funcionaram | A direção nunca foi lida (suposição de que o LMU não informava); a velocidade usava o módulo do vetor `mWind`, que pode estar zerado no jogo | Direção relativa ao carro (vetor `mWind` + orientação `mOri`), seta sem N/E/S/W (o LMU não tem norte), "--" se o vetor for zero, opção de inverter a seta, valores crus no log e no diagnóstico | **Baixa até ver o vetor real**: se o jogo não preenche `mWind`, o painel mostrará "--" |
| Janelas não ficaram sobre o jogo | O overlay já reafirmava "sempre no topo" a cada 1 s; causa mais provável é o jogo em **tela cheia exclusiva** (nenhum overlay aparece) | Reafirmação a cada 0,3 s; log/diagnóstico "janela do jogo LMU" (modo da janela, tela cheia, ordem acima/abaixo do overlay) | A confirmar com o log |
| (achado no log, não relatado) Alerta de amarela local acesa o tempo todo | `mSectorFlag` dos 3 setores vinha ≠ 0 durante toda a sessão | Só vale o valor 1; 3 setores juntos fora da amarela geral = dado suspeito (ignorado); valores crus no log | Média |

## 2. O que a sessão real confirmou (log de 23:03–23:18)
- **Pneus:** `mWear` 1,0 = pneu novo (desgaste cai com o uso) → suposição de "100 % = novo" correta. Temperaturas, pressões e freios coerentes. Após a pancada forte (força 5663) a roda dianteira esquerda foi dada como perdida (`mWear` 0, sem pressão), coerente com o impacto na frente-esquerda.
- **Energia virtual:** nível 94,8 %, consumo 2,67 %/volta, alcance 35 voltas, reposição a 100 % nos boxes — coerente.
- **Delta:** overlay × jogo diferiram 0,01 a 0,02 s em volta limpa (divergência grande só após a volta de box/incidente, esperado).
- **Gaps:** diferença mediana entre o intervalo medido pelo jogo e o calculado pela posição de 0,35 a 1,2 s (máx. 7,9 s em carros não vizinhos, marcados com "~").
- **Desempenho:** ciclo médio 0,8 ms, p95 2,2 ms, com 12 janelas visíveis.

## 3. Riscos e dependências
1. **Vento:** sem o valor real de `mWind` não dá para afirmar que o LMU o informa. O próximo log/diagnóstico traz o vetor.
2. **Sobreposição:** se o jogo estiver em Fullscreen, trocar para Borderless é a solução (não há contorno seguro sem injeção no jogo, que o projeto não faz).
3. **Danos:** zonas 3 a 7 e o espelhamento direito/esquerdo seguem pela mesma hipótese (anti-horário); testar direita, traseira e quinas.
4. **Amarela local:** a numeração/valores do `mSectorFlag` seguem a confirmar (log "bandeiras LMU").
5. Restrições do projeto mantidas: iRacing intocado (hashes idênticos), nenhum código de terceiros copiado.

## 4. Recomendação final
Verificar o modo de vídeo do LMU (Borderless), repetir a sessão de teste com as janelas visíveis, rodar `diagnostico_lmu.bat` com o carro na pista e enviar `diagnostico_lmu.txt` e `overlay_log_lmu.txt`. Com isso fecham-se vento, amarela e o restante do roteiro (testes 10 a 14).

## 5. Próximos passos
1. Conferir o modo de vídeo e a linha "janela do jogo LMU" do log.
2. Testes 12 (danos: direita, traseira, quinas), 13 (alertas, sem amarela falsa) e 3 (vento).
3. Enviar diagnóstico e log.
4. Depois: layout do Stream Deck XL para o LMU (adiado por decisão do autor) e Fase 21 só após a homologação do iRacing.

## Arquivos alterados na 1.3
`ov_lmu.py` (ordem das zonas, lado do impacto, bandeiras, vento, janela do jogo), `overlay_lmu.py` (versão 1.3, clima, logs, topo a 0,3 s, menu do vento, diagnóstico), `ov_janela_lmu.py` (JanelaClimaLMU), `ov_janelas_extra_lmu.py` (danos), `ov_demo_lmu.py` (classificação do demo corrigida; lado do impacto), `testes/teste_lmu.py`, `LEIA-ME_LMU.txt`, `ROTEIRO_VALIDACAO_LMU.txt`.

## Adendo — segundo teste real (1.3, 30/10/2026 23:36–23:49) e versão 1.3.1
- **Danos (CONFIRMADO):** a ordem anti-horária foi confirmada em 4 impactos: frente-esquerda → índice 1; frente-direita → índice 7; traseira-direita → índice 5. Faltam batidas nos índices 0, 2, 3, 4 e 6.
- **Amarela (CORRIGIDO na 1.3.1):** valores crus do jogo: **11 = sem amarela; 1 = amarela local** (ex.: `[11, 1, 11]`). A 1.3 classificava o 11 como "suspeito" (inofensivo, mas ruído); a 1.3.1 trata 11 como normal. A numeração dos setores ainda precisa ser comparada com a posição do incidente.
- **Vento (NÃO DISPONÍVEL):** `mWind` chegou **(0, 0, 0) o tempo todo** (sessão com chuva 0 e nuvens 0). O painel mostra "--". Falta testar uma sessão com clima dinâmico/chuva; se continuar zerado, o LMU não expõe o vento por essa memória compartilhada e a direção sai do escopo. O diagnóstico agora consulta (só leitura) a API local do jogo (porta 6397) para ver se ela traz previsão/vento.
- **Janela por cima do jogo (PENDENTE):** o log mostra o jogo em 3440×1440, sem borda, em (0,0), com o overlay **acima** do jogo na ordem das janelas, mas o usuário não vê as janelas. O Windows não diferencia Borderless de tela cheia exclusiva por esses dados. Causa mais provável: modo de janela do jogo (Graphics > Window Mode) em Fullscreen, ou conflito de composição de vídeo. A 1.3.1 passa a registrar também qual programa está em primeiro plano.

## Adendo 2 — versão 1.3.2 (sobreposição em Borderless)
- **Fato informado pelo usuário:** as janelas aparecem por cima do jogo **só no modo Window**; em Borderless/Fullscreen não aparecem (por isso os testes foram feitos em Window).
- **Hipóteses:** (a) o jogo, em Borderless, reafirma "sempre no topo" a cada quadro e vence a reafirmação do overlay; (b) o jogo usa apresentação direta (flip independente) e o Windows não compõe janelas sobre ele; (c) o DWM esconde as janelas ("cloaked"). Em Fullscreen exclusivo (c/b) nenhum overlay funciona.
- **Mudanças 1.3.2 (somente arquivos do LMU):** reafirmação do topo a cada 0,1 s e imediatamente a cada mudança de foco (gancho de evento do Windows, leitura/ordem de janelas do próprio overlay; nada é injetado no jogo); novo log a cada 60 s `sobreposicao LMU: ... jogo ACIMA do overlay em X% ... cloaked em Y%` que separa as hipóteses: X alto = briga de topo (a 1.3.2 deve resolver); X≈0 e Y≈0 com janelas invisíveis = o jogo não deixa janelas de outros programas aparecerem (limite do modo de vídeo do jogo; usar Window).
- **Teste pedido:** 2 a 3 minutos em Borderless com o jogo na pista e o overlay aberto; enviar `overlay_log_lmu.txt`.

## Adendo 3 — terceiro teste real (1.3.2, 31/10/2026 00:04–00:18) e versão 1.3.3
- **Sobreposição (CONCLUÍDO):** com o jogo em **Fullscreen**, o log mostrou o jogo **acima** do overlay em 0–1% do tempo e janelas escondidas pelo DWM em 0%: a ordem das janelas está correta, mas a tela cheia exclusiva ignora a ordem do Windows. **Não há solução sem injeção no jogo (fora do projeto).** Modo certo: **Window** (aparece como janela sem borda 3440×1440) ou Borderless.
- **Vento (ENCERRADO):** `mWind` = (0, 0, 0) também com chuva 0,15, nuvens 3 e pista 100% úmida. O LMU não preenche o vento nessa memória. O painel mantém "--". Resta só o teste do `diagnostico_lmu.bat` (consulta à API local, porta 6397).
- **Danos (CONFIRMADO):** zonas 0 (frente), 1 (frente-esquerda), 4 (traseira), 5 (traseira-direita), 6 (direita) e 7 (frente-direita) conferidas com impactos reais; faltam 2 (esquerda) e 3 (traseira-esquerda). O "lado do impacto" foi recalibrado: nas faces da frente e da traseira (|z| ≥ 2,1 m) vale frente/traseira, inclusive no canto.
- **Amarela (CONFIRMADO):** 11 = sem amarela; 1 = amarela local, nos setores de índice 0, 1 e 2 (várias ocorrências).
- **Pendente do usuário:** conferir se o índice do setor da amarela corresponde ao setor do incidente.
