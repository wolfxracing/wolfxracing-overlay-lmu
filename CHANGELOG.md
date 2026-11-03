# Histórico de versões

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e [SemVer](https://semver.org/lang/pt-BR/).

## [1.6.3] - 2026-11-03

Revisão de código externa (ChatGPT) triada e validada antes de aplicar. Nenhuma mudança visual.

- **Corrigido:** um painel com erro na atualização não impede mais os painéis seguintes de receberem dados (isolamento por janela; o erro vai para `overlay_log.txt`).
- **Corrigido:** `config.json` agora é gravado em arquivo temporário e trocado de forma atômica; uma falha de gravação preserva a configuração anterior e passa a ser registrada no log (antes era silenciosa).
- **Corrigido:** ao desligar os atalhos globais, se a escuta não encerrar a tempo ela é mantida e registrada, em vez de esquecer uma thread ainda viva.
- **Melhorado:** a Classificação só refaz o layout quando a classificação muda (os dados chegam a 2 Hz, a janela atualiza a 30 Hz).
- **Melhorado:** o aviso de desempenho não ordena mais as amostras quando o ciclo está dentro do orçamento.
- Novo teste automático `testes/teste_v163.py`.

## [1.6.2] - 2026-11-03

- **Corrigido:** **Corvette** passa a usar o emblema próprio (`corvette.png`) em vez do da Chevrolet quando o carro é um Corvette ("Chevrolet Corvette Z06 GT3.R" no LMU, "Chevrolet Corvette C8.R" no iRacing). A Camaro e outros Chevrolet continuam com `chevrolet.png`.
- **Novo:** a marca **Duqueine** (LMP3 do LMU) é reconhecida e procura `duqueine.png`.
- **Corrigido:** a lista `emblemas_faltando.txt` (`emblemas_faltando_lmu.txt` no LMU) é apagada ao abrir o overlay e passa a listar só as marcas que aparecerem na sessão. Evita sobras de versões antigas, como nomes de equipe do LMU (13, CLX, Manthey...), que já não são tratados como marca desde a 1.5: no LMU a marca vem do modelo do carro, nunca da primeira palavra.
- Novo teste automático `testes/teste_marcas.py` (marcas de iRacing e LMU, nomes de equipe e limpeza da lista).
- Os emblemas das montadoras continuam fora do pacote público (marcas registradas): cada usuário coloca os seus em `emblemas/`.

## [1.6.1] - 2026-11-02

- **Novo:** **Classificação no layout de transmissão** (arquivo novo `ov_classif_foto.py`; mesma linguagem visual do iRacing). Barra superior (sessão, tempo, volta, AIR, TRACK, número de carros); colunas POS, +/-, #, marca, DRIVER, selos PIT/PEN/FIM/DNF/DSQ, GAP, INT, BEST, LAST, AVG 5, PIT (paradas) e FUEL (%). Seu carro em roxo. Sem licença/iRating, pneu e bandeira, porque o LMU não informa. GAP/INT cinza com "~" continuam sendo estimativa.
- **Configuração (opcional):** `classificacao_layout` = `"classico"` volta à janela antiga (1.6.0).
- **Novo:** **versão EXE, sem precisar de Python.** Cada release traz `WolfxRacing_LMU_vX.Y.Z_EXE.zip` (pasta única; config, logs e emblemas ficam ao lado do `.exe`). Também dá para gerar no seu PC com `overlay\gerar_exe_lmu.bat`. O EXE não tem assinatura digital paga: o Windows SmartScreen pode avisar ("Mais informações" > "Executar assim mesmo").
- Novos arquivos: `ov_classif_foto.py`, `wolfx_lmu.spec`, `gerar_exe_lmu.bat`, `exe_modelo_lmu/`, `wolfxracing.ico`, `tools/notas_release.py` e o fluxo `.github/workflows/release.yml`.

## [1.6.0] - 2026-11-02

- **Novo:** **Central de configurações**: janela interativa (duplo clique no ícone da bandeja, ou "Abrir configurações…"). Cartões com prévia, liga/desliga, busca e filtros; "Personalizar" abre o tamanho, as opções do painel e a prévia ao vivo; páginas de Aparência e sistema. Usa os mesmos itens do menu: atalhos do Stream Deck e perfis continuam valendo. O menu da bandeja ficou curto (Abrir configurações, Travar posição, Todas as opções, Sair); o menu completo é o submenu "Todas as opções (avançado)".
- **Novo:** janela **Último contato**: quem você tocou por último (o LMU não informa pontos por carro; volta, há quanto tempo e onde o piloto está agora em segundos). Detectado pelo impacto do jogo com um carro encostado (até 7 m).
- **Novo:** janela **Entrada do pit**: distância até a entrada dos boxes, aviso FREIE (distância de frenagem estimada até o limite) e, na pit lane, velocidade contra o limite e distância até o seu box. A entrada é aprendida na primeira vez que você entra por pista (arquivo `pit_entradas.json`); aparece com parada pedida ou com a opção "mostrar sempre".
- Visual da Central e ícone da bandeja com a marca WolfxRacing (pasta `overlay/marca/`: logos originais, sem alteração, e imagens de cenário). A marca é identidade do projeto; veja o NOTICE.
- **Corrigido:** **Minimapa rotativo** travando. Desenho a 60 quadros por segundo no relógio próprio, posição estimada entre as leituras do jogo, rotação feita pelo Qt sobre um caminho montado uma única vez e rumo contínuo (antes girava em degraus). No modo economia de CPU desenha a metade dos quadros.
- 23 janelas no total. Novos arquivos: `ov_v16.py`, `ov_central.py`, pasta `marca/`.

## [1.5.0] - 2026-11-02

- **Novo:** **Bandeiras**: faixa com a bandeira da pista (verde por 6 s, amarela, amarela de pista inteira, azul, branca, quadriculada, preta/desclassificado, vermelha). Só aparece quando há bandeira.
- **Novo:** **Tráfego de outras classes**: só aparece com carro de outra classe a até ~6 s, com a diferença em segundos (▼ atrás / ▲ à frente; vermelho quando uma classe mais rápida chega por trás). Os segundos são calculados pelo overlay.
- **Novo:** **Minimapa rotativo**: trecho da pista ao redor do seu carro, girando para ele apontar sempre para cima, com os carros na cor da classe e o "N". Alcance 150/260/400 m no menu. O traçado é aprendido na primeira volta (o jogo informa a posição no mundo no LMU); é uma inferência.
- **Novo:** **Auxiliar de sessão**: etapa (grid, volta de apresentação, luzes), contagem/duração e tempo restante ao fim. Durante a sessão só aparece com "Auxiliar: também durante a sessão".
- **Corrigido:** o radar da 1.4.2 podia piscar no modo automático (conflito com o laço principal). Todas as janelas automáticas (radar, bandeiras, tráfego, auxiliar) usam agora a mesma lógica sem piscar.
- 21 janelas no total; sem atalhos de Stream Deck para as novas nesta versão.

## [1.4.2] - 2026-11-02

- Radar e classificação do iRacing receberam melhorias (radar automático, aviso de carro ao lado, coluna +/− de posições ganhas e perdidas); a janela de classificação do LMU não mudou.
- **Melhorado:** Telemetria em barra mais compacta (620 × 88 px; 292 px sem o gráfico) com colunas de pedal finas.

## [1.4.1] - 2026-11-02

- **Novo:** layout opcional **em barra horizontal** para a janela Telemetria (menu da bandeja: "Layout em barra horizontal"). Uma linha só, 620 × 88 px (compacta, colunas de pedal finas): volante, marcha, velocidade, pedais com o valor numérico e gráfico. Cores: embreagem azul, freio laranja, acelerador verde. Sem o gráfico a barra tem 292 px. O painel de antes continua sendo o padrão.

## [1.4.0] - 2026-11-02

- **Novo:** janela **Curvas** (a 17ª): velocidade mínima em cada curva, comparada com a sua melhor passagem por ela. Mostra MIN, BEST, DELTA (verde = mais rápido que a melhor passagem, vermelho = perdeu 3 km/h ou mais) e o ângulo do volante no ponto da velocidade mínima, mais as últimas curvas da volta e o que a volta anterior ganhou e perdeu.
- As curvas são achadas sozinhas a partir da velocidade em cada trecho da pista (a primeira volta válida cria o mapa; três voltas o refinam e ele congela). Volta válida = sem boxes, fora da pista, parada ou muito lenta. Tudo vem do carro; o mapa de curvas é uma inferência (curvas muito suaves não aparecem).
- Valores só da sessão (sem gravar por pista); sem atalho de Stream Deck nesta versão. Menu da bandeja: ligar/desligar, escala e "reiniciar o aprendizado desta pista".
- Inclui tudo da 1.3.1 (montadoras pelo modelo, `preparar_emblemas`, recortes).
- Montadoras reconhecidas também: Holden, Caterham e Ginetta (somente o nome; os emblemas continuam fora do repositório).

## [1.3.1] - 2026-11-02

- **Corrigido:** a **montadora** do carro agora é reconhecida também pelo **modelo** (Vantage, 911, 296, Z06, M4, 9X8, A424, V-Series.R, GMR-001...) e **não cai mais na primeira palavra** do nome, que no LMU costuma ser a equipe. Antes a lista `emblemas_faltando_lmu.txt` enchia de nomes como `heart`, `team`, `inter`, `13`; agora só aparecem montadoras. Carro sem montadora reconhecida mostra `--`.
- **Novo:** montadoras do LMU na lista de marcas: Alpine, Corvette, Glickenhaus, Vanwall e Isotta Fraschini.
- **Novo:** `preparar_emblemas.bat` / `preparar_emblemas.py`: pega imagens soltas (PNG, JPG, WEBP, SVG) da pasta `emblemas\novos`, corta as bordas, centraliza num PNG quadrado transparente de 256 px e salva em `emblemas` com o nome certo; logos pretos viram brancos (fundo do overlay é escuro; `--nao-clarear` desliga). Para logos que vêm com o nome escrito junto, um `recortes.json` na pasta `novos` diz que parte da imagem guardar (só o símbolo) e quais marcas clarear.
- Os emblemas continuam **fora do repositório** (são marcas registradas).

## [1.3.0] - 2026-11-01

- **Novo:** botões de **Stream Deck** para as quatro janelas da 1.2.0: **Luz ABS**, **Luz TC**, **Retorno** e **Estratégia** (linha de baixo da página principal, posições 3,3 a 6,3). O perfil `Overlay LMU.streamDeckProfile` foi regenerado (30 botões na página principal) e os quatro ícones ficam na biblioteca.
- **Novo:** atalhos globais `Alt+Shift+F21` (Luz ABS), `Alt+Shift+F22` (Luz TC), `Alt+Shift+F23` (Retorno) e `Alt+Shift+F24` (Estratégia). Entram no fim da tabela `ATALHOS_LMU`, então os 20 atalhos antigos não mudam; são 24 no total. Não colidem com os do overlay de iRacing (que usa `Alt+F13..F16` para as mesmas quatro janelas).
- Quem já importou o perfil antigo: importe de novo (ou crie os quatro botões na mão com a ação *Hotkey*); os demais botões não mudam.
- Sem mudança nas janelas, nos dados nem na configuração. Testes de atalhos atualizados para 24.

## [1.2.0] - 2026-11-01

- **Alterado:** a janela **Telemetria** passou a ter o gráfico de pedais rolante por tempo (5 a 30 s), com degraus da marcha e marcas de ABS (amarelo) e TC (azul), ambas do próprio jogo.
- **Novo:** **Luz do ABS** e **Luz do TC**: ícones soltos que acendem quando o jogo informa ABS ou TC atuando (`mABSActive`, `mTCActive`); cor, modo de piscar e teste de 5 s. No LMU não é estimativa.
- **Novo:** **Retorno à pista**: PARE / CEDA / LIVRE e os segundos até o carro mais próximo que vem atrás chegar até você; não avisa nos boxes, no grid nem na volta de apresentação. Limites ajustáveis.
- **Novo:** **Estratégia de pneus** (chuva x seco): SEGUIR / PREPARE-SE / TROCAR pela umidade da pista, chuva e pneu montado; pneu para largar. O LMU não informa o pneu dos outros carros, então não há vantagem estimada nem contagem de rivais.
- Base do overlay atualizada para a do iRacing 1.2.0 (novo módulo `overlay/ov_v12.py`); 16 janelas no total. Nova suíte `testes/teste_lmu_v12.py`.
- Sem atalhos de Stream Deck para as quatro janelas novas nesta versão (use o menu da bandeja).
- Testado só com jogo simulado: a validação com o LMU real (principalmente Luz do TC, Retorno e chuva) está no `ROTEIRO_VALIDACAO_LMU.txt`, teste 16.

## [1.1.0] - 2026-11-01

- **Novo:** estilo visual **Glass Fumê** (vidro escuro translúcido, reflexo suave, bordas finas, com tipografia esportiva itálica). É o novo padrão do overlay; o Sport continua disponível em *bandeja > Estilo Sport* (os dois são excludentes).
- **Novo:** dash **MagicDash 4 LMU Glass** (3 telas) ao lado do Sport; gerado com `build_sport.py --vidro`.
- Config: nova chave `tema_vidro` (padrão ligado). Quem já tinha o Sport ligado passa a ver o Glass Fumê e pode voltar ao Sport pela bandeja.
- Sem mudanças na leitura de telemetria nem no perfil do Stream Deck.

## [1.0.0] - 2026-11-01

- Primeira versão pública. Base: overlay LMU **1.6.0 Sport** sobre o overlay iRacing Fase 20.2.2.
- 12 janelas: telemetria, voltas, classificação detalhada por classe, clima, combustível, força G, energia virtual, pneus e freios, danos, alertas na pista, stints e tendência de ritmo.
- **1.5.2:** alerta **MOTOR PARADO** (ignição ligada sem rotação, igual à luz do painel do jogo); linha **FAROL** na janela Danos; desgaste de pneu `mWear = 0.0` exato tratado como *sem leitura*; log de impacto limitado a 1 linha a cada 5 s.
- **1.6.0:** estilo visual **Sport**.
- **Novo:** dash **MagicDash 4 Sport** (3 telas) com energia virtual e **posição na classe** (via plugin Lovely).
- **Novo:** perfil de Stream Deck XL com caminho ajustável (`ajustar_perfil.py`).
- Pacote limpo de dados pessoais e de marcas registradas; documentação e manual com prints.

O histórico detalhado de desenvolvimento (relatórios por fase) está em [docs/historico](docs/historico).
