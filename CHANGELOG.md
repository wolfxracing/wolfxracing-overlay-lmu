# Histórico de versões

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e [SemVer](https://semver.org/lang/pt-BR/).

## 1.8.2 build ba (corretiva - auditoria da v1.8.1 / build az)
- Fontes: as fontes Orbitron, Michroma e Bungee e a licenca OFL agora vao DENTRO do pacote do EXE (`fontes/` em `_internal`). O carregador procura primeiro na pasta do EXE e depois no pacote; nova opcao `--verificar-fontes` carrega as fontes, confere que cada uma e APLICADA (a tinta muda em relacao ao padrao) e grava `fontes_verificacao.json`. O workflow extrai o ZIP em pasta limpa e executa essa verificacao antes de publicar.
- Classificacao Foto (iRacing e LMU): o texto da sessao (PRACTICE/TREINO), o clima (AIR 24 graus), INC e o contador passam a ser medidos, reservados e desenhados pela tinta real do texto; so deixam de ser recortados pelo retangulo quando o recorte comeria pixels. A pilula da sessao so cresce quando a tinta exige; aparencia padrao preservada. Teste novo `teste_v182_classif_foto_recorte` compara o que foi efetivamente pintado (inclusive bordas) com uma referencia sem recorte: Michroma/Orbitron/Bungee a 200%, negrito, italico, largura normal e minima.
- Atualizador do LMU (so repositorio LMU): travas distinguem ATIVA de ORFA (processo morto, trava com mais de 6 h ou vazia/antiga); trava ativa devolve codigo 4, inclusive em `--simular` (antes `--simular` dizia sucesso e a execucao real falhava); trava orfa e removida. Atualizador e manifesto sao gerados a partir do MESMO commit do codigo, e o workflow compara o conteudo antes de publicar. Teste novo `teste_v182_atualizador_lmu` (30 verificacoes: trava ativa/orfa, preservacao de dados do usuario, backup, idempotencia, reversao com arquivo realmente travado no Windows).
- Publicacao: `release.yml` valida o SHA da tag, a versao interna e o commit do artefato; exige a suite de testes obrigatoria (Windows nativo) antes de publicar; gera o SHA-256 no mesmo fluxo; cria a release como rascunho, confere os digests enviados e so entao publica; nao sobrescreve release existente.
- Testes - causas separadas do produto: (a) `teste_v18_i18n` dependia do idioma da maquina (ja_JP -> en); agora isola o ambiente e documenta a precedencia; (b) as suites do LMU registravam atalhos globais reais e falhavam quando o ambiente restringe isso; agora sao hermeticas; (c) `teste_v18_posicao_fonte` dependia do relogio real; agora usa relogio congelado.
- Versao do produto 1.8.2. Telemetria, calculos de corrida e configuracoes dos usuarios nao foram alterados. As tags/assets v1.8.0 e v1.8.1 sao preservados.
- **Sem homologacao em simulador real e sem teste com Stream Deck real.** Validacao com dados sinteticos e renderizacao Qt.

## 1.8.1 build az (corretiva - auditoria da build ay)
- Fontes: a sonda que decide se o negrito muda o desenho da fonte do tema passou a aceitar uma lista de familias (tema, alternativas do tema e, por fim, a Rajdhani embutida) e ficou muito mais rapida (leitura direta dos pixels; mediana de 27,73 ms para 0,18 ms com cache vazio, medida no Windows pela auditoria). As 28 decisoes de peso comparadas permaneceram iguais. Orbitron em italico passa a respeitar o peso pelo eixo variavel (wght).
- Executor de testes: rodar_todos_os_testes.py ganhou --plataforma windows|offscreen (registrado em AMBIENTE.txt e RESUMO.txt). Testes de cronograma deixam de depender de time.tzset() (inexistente no Windows): sem tzset usam o fuso fixo BRT3 e as verificacoes de horario de verao sao PULADAS com aviso explicito. As suites de cronograma tambem passam a PULAR (com aviso) as verificacoes que usam o cronograma.json real, dado do usuario que nao e versionado; os demais passos usam dados sinteticos.
- Executor de testes (causa de travamento achada): a trava de instancia unica do overlay (overlay_iracing*.lock) fica na pasta temporaria do sistema; com ela compartilhada, a suite teste_fase2022 ficava esperando se outra execucao (ou o overlay aberto em demo) a segurasse. Cada suite agora roda com a SUA pasta temporaria (TMP/TEMP/TMPDIR); dois pacotes em paralelo passam.
- Versao do produto 1.8.1 (a tag v1.8.0 ja estava publicada). Telemetria, calculos de corrida e configuracoes dos usuarios nao foram alterados.
- Classificacao LMU (cabecalho): fonte e metricas reaproveitadas dentro de cada desenho (reducao de 4,8% a 11,4% no tempo de desenho do cabecalho nos cinco cenarios medidos pela auditoria, imagens identicas); sessao (RACE) do layout foto respeita o contador de carros; a ancora padrao volta a ser identica a referencia congelada da au, mantendo a correcao de saliencia nos itens personalizados.
- Atualizador completo do LMU (atualizar_lmu.py): confere inventario e SHA-256 do manifesto ANTES de escrever no destino (origem incompleta ou divergente e recusada), copia em area temporaria no mesmo volume e reverte as alteracoes do programa se um arquivo estiver bloqueado; codigo de saida 3 = reversao incompleta. verificar_migracao.py valida a migracao a partir da ae numa copia isolada.
- Sem homologacao em simulador real; os testes visuais usam dados sinteticos e renderizacao Qt.

## 1.8.1 build ay (correcoes da auditoria da build ax)
- Classificacao LMU, cabecalho (foto): o total de carros mede, reserva e desenha pela AREA REAL do texto renderizado (tinta com saliencia de italico e glifos altos, sem recorte). O indicador de sessao (RACE) respeita o espaco do contador. Regra previsivel: o contador tem prioridade; o que nao cabe INTEIRO some (nada pela metade); se o contador sozinho nao cabe na barra, ele e que some. Testado com 180 px, 210 px e largura normal, Orbitron/Michroma 200% com negrito e italico, 62 e 100 carros.
- Classificacao LMU, cabecalho (classico): tempo/volta, temperaturas e total de carros sao medidos EM CONJUNTO com o estilo de cada item; prioridade tempo/volta > contador > temperaturas; a reserva do contador e liberada quando ele esta oculto ou sem espaco.
- Negrito + italico visiveis: se o Qt nao muda o peso da fonte do tema (Bahnschrift variavel no Windows), a escolha de negrito usa a familia seguinte do tema (Segoe UI). Aparencia padrao intacta.
- LMU: o icone alternativo da bandeja passa o proprio QPainter a fonte() (nao herda a fonte de outro pintor).
- Entrega: pacote COMPLETO de atualizacao do LMU (serve a partir de qualquer build anterior, com backup, SHA-256 e rollback); rodar_todos_os_testes.py (codigo de saida por teste, falha final) e requirements-teste.txt (PySide6 + NumPy).
- Sem homologacao em simulador real.

## 1.8.1 build ax (correcoes da auditoria da build aw)
- Fonte e cor isoladas por QPainter (iRacing e LMU): fonte(), fonte_titulo(), _cor_do_elemento() e _estilo_do_elemento() passam a consultar o estilo do PINTOR que mede/desenha. Dois pintores abertos ao mesmo tempo nao se misturam (A com Orbitron 150% negrito italico vermelho mede e desenha 30 pt, B com Bungee 60% regular azul, 12 pt). Todas as chamadas de desenho dos paineis passam o pintor; a pilha de cores da aw ficou intacta.
- LMU, Classificacao - total de carros: o contador (N CARS / N CARROS) mede, reserva espaco e desenha com a fonte EFETIVA do proprio item. Foto: a area fixa de 120 x 20 acompanha o texto (sem corte com 62 carros e Orbitron 200%), alinhada a direita como antes. Classico: a folga das temperaturas usa a largura real do contador (sem sobreposicao com 62 carros e Orbitron 150%) e e liberada quando o contador esta oculto.
- Testes: teste_v18_cores_aninhadas (caso 6 reescrito, 78 verificacoes) e teste_v18_ncars_lmu (novo, 137). Sem homologacao em jogo real.

## 1.8.1 build aw (correcoes da auditoria da build av)
- P2.1 Janelas exclusivas do LMU com itens individuais (posicao X/Y, fonte, negrito, italico, tamanho, cor, liga/desliga): Energia e combustivel, Pneus e freios, Danos, Alertas na pista, Historico de stints e Tendencia de ritmo. Desenho, calculos e comportamento padrao inalterados (imagem identica a da build au). Classificacao do LMU: N CARS agora e um item (o espaco reservado na barra acompanha a fonte escolhida) e o layout classico tambem tem itens (legenda, sessao, tempo e volta, temperaturas, N CARROS, titulos, faixas de classe, linhas). Itens Clima e Incidentes saem da lista da Classificacao do LMU (nunca eram desenhados la).
- P2.2 Isolamento de pintores reentrante: a pilha de itens guarda o estado POR PINTOR (referencia fraca). Abrir/fechar itens em um pintor nao toca nos itens abertos de outro (A abre, B abre, B fecha, A continua com a sua cor/fonte); so restos de pintores ja encerrados sao descartados. Transparencia, degrades e excecoes preservados.
- P2.3 teste_v18_itens_todos_paineis reforcado: persistencia com salvar_config/carregar_config REAIS (config.json gravado e recarregado: X/Y, fonte, tamanho, estilo, cor, visibilidade), dimensao esperada (tamanho() x escala e valores da build au), imagem padrao comparada com a referencia CONGELADA da build au (arquivos da au em outro processo, hash conferido), 6 janelas do LMU + Classificacao LMU (foto e classico) incluidas, cada propriedade verificada em cada cenario de dados em que o item aparece, relogios congelados.
- Defeito achado pelo teste de persistencia (vinha de builds anteriores): posicao e estilo dos itens do Delta Trace eram gravados mas descartados ao reiniciar; agora sobrevivem.
- Catalogo i18n: 1029 entradas (+47). Sem homologacao em jogo real.

## 1.8.1 build av (correcoes da auditoria da build au)
- P1.1 Cor por item com itens aninhados: cada item guarda os metodos que havia antes e os devolve ao fechar; a cor de dentro vale so dentro e, ao fechar o interno, volta a cor do externo. Embrulhos com referencia fraca ao pintor (sem ciclo que segure o QPainter), sobras de um desenho que falhou sao descartadas e desfeitas, pintores/janelas diferentes nao interferem. Transparencia e degrades preservados.
- P1.2 Coach: contagem (proxima), curva e distancia (freada), marcha e apice funcionam cada um sozinho; a faixa de cima so some quando os quatro estao desligados. Desenho padrao identico ao da build au.
- P2.1 Dependencias explicitas (DEPENDE): Mapa de vazao (marcador e trilha sobre o mapa), Eficiencia por marcha (parcela, RPM maximo e RPM atual sobre a grade) e Destino do combustivel (cabecalho de RPM na tabela). Na Central o item dependente aparece com "(depende de: ...)" e fica desabilitado enquanto o de fora estiver desligado. Pneus: "detalhes" agora e independente de "vida"; Classificacao: sessao, contadores, clima e incidentes sao independentes da "barra" (que passa a ser so o fundo).
- P2.2 Classificacao: o espaco de sessao, clima, incidentes e contadores e medido com o estilo real do item (fonte, negrito, italico, tamanho ate 200 %); sem sobreposicao em pt, de e fr.
- P2.3 Novos itens (posicao, fonte, tamanho e cor) em Mapa da pista, Forca G, Luz do ABS, Luz do TC, Trafego, Minimapa rotativo, Ultimo contato e Entrada do pit. O desenho principal (pista do Mapa/Minimapa, disco da Forca G) continua fixo.
- P2.4 Teste novo teste_v18_itens_todos_paineis: cada item de cada painel e verificado propriedade a propriedade (X, Y, fonte, negrito, italico, tamanho, cor, visibilidade), persistencia em JSON e restauracao; item/propriedade sem efeito faz o teste falhar. Itens sem texto (ou so com traco/degrade) estao listados no proprio teste como nao aplicaveis.
- P3 Central: "Tam. padrao" e um valor a parte (49) e 50 % passa a ser um tamanho real.
- Qualidade: teste_v18_telemetria_ordem deterministico (tempo congelado e temporizador da previa parado), 6 execucoes paralelas sem falha. Correcoes achadas pelo novo teste: fonte do numero do Relativo e do numero no Minimapa passaram a respeitar o estilo.
- Testes novos: teste_v18_cores_aninhadas (24), teste_v18_classif_barra_fontes (295). Catalogo i18n: 982 entradas. Sem homologacao em jogo real.

## 1.8.1 build au (itens com posicao e estilo em TODOS os paineis; 19 correcoes da validacao da build at)
- Previa ao vivo da Central agora acompanha cada opcao: Relativo (iRating X/Y, fontes, distancia em segundos, nome), Pneus (zonas, vida e rodape), Velocidade nas curvas (titulo e contador), Tendencia de ritmo (titulo e selo de estado), Mapa de vazao (trilha da posicao), Calendario (fechamento do registro), Energia hibrida (estado) e Tempo da sessao (barra de progresso e percentual).
- Paineis que ganharam itens com posicao (X/Y), fonte, negrito/italico, tamanho e cor: Classificacao (barra superior, tipo da sessao, contadores, clima, incidentes, titulos, faixa de classe, linhas), Radar (faixa, brilho, aviso, carros, seu carro, distancias, nota), Voltas (calculo de combustivel: voltas ate o fim, necessario e adicionar), Danos e impactos, Combustivel e pit, Retorno a pista, Estrategia de pneus, Bandeiras, Auxiliar de sessao e Delta Trace (grafico, volta anterior, ritmo ideal, blocos, numero da curva, desenho da pista).
- Coach ao vivo: itens separados para a contagem grande, curva e distancia da proxima freada, marcha da curva, velocidade no apice, delta, ritmo, dica da melhor curva e rodape.
- Estrategia de pneus: o texto do nivel da pista (ex.: "Pouco molhada") nao encosta mais na barra de nivel.
- Pedais do Coach: a previa mostra um exemplo (freio, acelerador, alvo e plano da curva) quando ainda nao ha referencia, para ver o que cada ajuste muda.
- Cor: alem do texto, agora tambem pinta os preenchimentos solidos do item (barras, selos, marcadores). Degrade e transparencia continuam como estao.
- Teste novo: teste_v18_itens_todos_paineis (todo item de todo painel muda a previa ao mover, trocar fonte/tamanho ou cor). Catalogo i18n: 957 entradas. Sem homologacao em jogo real.

## 1.8.1 build at (posicao livre e estilo de cada item, em todos os paineis com itens)
- Central: nos paineis com itens (Elementos), novo bloco "POSICAO E ESTILO DOS ITENS": arraste qualquer item direto na previa (horizontal e vertical, encaixe de 2 px) ou ajuste X e Y; por item: fonte de corrida, negrito/italico, tamanho (50 a 200 %) e cor do texto. Botao "Restaurar posicoes e estilos".
- 9 fontes de corrida embutidas na pasta fontes/ (licenca OFL, texto em fontes/LICENCAS_OFL.txt): Racing Sans One, Russo One, Audiowide, Rajdhani, Chakra Petch, Orbitron, Michroma, Share Tech Mono, Bungee. Simbolos que a fonte nao tem (como o grau) caem na fonte do tema.
- Telemetria: cada bloco (volante, marcha, velocidade, pedais, grafico, barra de RPM) tambem ganha posicao e estilo, alem da ordem da build as.
- Cobertura: Telemetria e 20 paineis que declaram itens. Itens do Delta Trace (grafico, curva, mapa, blocos) e zonas/vida do Pneus ainda nao se movem. Paineis sem itens declarados (ex.: Radar, Minimapa, Mapa, Luz ABS/TC, Combustivel, Danos, Estrategia, Forca G) ficam para a proxima etapa.
- Chaves de config: elementos_<painel>_pos ({item: [x, y]}) e elementos_<painel>_estilo ({item: {fonte, cor, negrito, italico, tam}}); valores invalidos sao ignorados. Sem configuracao o desenho e identico ao anterior.
- Teste novo: teste_v18_posicao_fonte (78 verificacoes). Catalogo i18n: 899 entradas. Sem homologacao em jogo real.

## 1.8.1 build as (Telemetria: ordem dos itens personalizavel)
- Telemetria: em Central > Telemetria, bloco "ORDEM DOS ITENS DA TELEMETRIA", cada item muda de posicao com as setas (◀ ▶), com a previa mudando na hora. Itens da barra: volante, marcha, velocidade, pedais e grafico; do painel: marcha, velocidade e RPM, pedais e volante. Ex.: volante a direita e pedais entre a marcha e o volante. Botao "Ordem original".
- Cada layout (barra e painel) guarda a sua propria ordem (chaves 'telemetria_ordem_barra' e 'telemetria_ordem_painel'); a janela nao muda de tamanho e, sem configuracao, o desenho e identico ao anterior (conferido pixel a pixel). Ids invalidos ou repetidos sao ignorados.
- Teste novo: teste_v18_telemetria_ordem (35 verificacoes, inclui todas as permutacoes dos dois layouts); catalogo i18n com 887 entradas. Calculos, Coach e demais paineis inalterados. Sem homologacao em jogo real.

## 1.8.0 build ar (corretiva - auditoria da build aq)
- P2: ao trocar o idioma na Central aparece o mesmo aviso de reinicio do menu da bandeja (ov_i18n.AVISO_REINICIAR, no idioma escolhido), pois a Central e os menus so traduzem por completo apos reiniciar.
- P3: a traducao passa a cobrir tambem argumentos nomeados de texto (text, title, toolTip, string, label) nas chamadas interceptadas, p.ex. QLabel(text=...), QMenu(title=...). Identificadores internos (objectName, propriedades) nunca sao traduzidos. Nota: os setters do PySide (setText etc.) nao aceitam argumentos nomeados; so os construtores.
- Teste: teste_v18_i18n passa a 50 verificacoes (8 novas: kwargs, identificadores preservados, aviso na Central). Catalogo (877 entradas), Coach, Danos, Cronograma, Classificacao e calculos inalterados.

## 1.8.0 build aq (multi-idioma: Português, English, Español, Deutsch, Français, Italiano)
- Idioma novo da interface: automatico pelo idioma do Windows na primeira execucao (se o Windows estiver em outro idioma, usa English); a variavel de ambiente WOLFX_IDIOMA forca o idioma automatico e troca manual em Central > Aparencia e sistema > IDIOMA / LANGUAGE e no menu da bandeja > Idioma / Language. Chave de config 'idioma' ("auto", pt, en, es, de, fr, it).
- Painéis e janelas do jogo trocam de idioma na hora; a Central e os menus da bandeja passam a usar o novo idioma ao reiniciar o overlay (o aviso aparece ao trocar).
- Implementacao: traducao na saida (ov_i18n.py + ov_i18n_catalogo.py, ~880 entradas). O texto em portugues continua sendo a origem; o que ainda nao tem traducao aparece em portugues, sem erro. Os calculos, o log e os arquivos de dados nao mudam.
- Cobertura por etapas: paineis, Central, menus, avisos e textos do Coach/Pedais/Calendario/FOV cobertos nesta build; restam textos longos de ajuda da Central e frases de status raras (aparecem em portugues). A voz falada (ov_voz) continua em portugues.
- Janela Pedais do Coach: a linha do plano agora usa duas linhas (nao corta mais "acel saida").
- Teste novo: teste_v18_i18n (42 verificacoes: deteccao do idioma do Windows, fallback, modelos {} / {#}, texto composto, troca em tempo de execucao). Sem homologacao em jogo real.

## 1.8.0 build ap (Coach: % de freio, trail braking e janela Pedais do Coach)
- Coach ao vivo: a linha da proxima zona mostra a % de pico de freio (F), o acelerador de saida (A) e "trail" quando a referencia freia soltando aos poucos (trail braking). Calculo novo e separado: as zonas e notas ja auditadas nao mudam.
- Janela nova "Pedais do Coach" (Central > Pilotagem; menu da bandeja): instrucao grande FREIE / TRAIL BRAKING / SOLTE O FREIO / SOLTE O ACELERADOR / ACELERE / PE FUNDO, com a % alvo da referencia (olha ~0,35 s a frente), barras de freio e acelerador com a SUA % ao vivo e a marca de onde a referencia estava, e o plano da proxima freada (% de freio, trail em metros e % do acelerador na saida da curva). Desligada por padrao.
- Posicao livre (arraste destravado) e "Centralizar na tela (horizontal)" no menu da bandeja; a janela tambem tem escala e elementos liga/desliga como as demais.
- Avaliacao da curva ganha a linha "Freio 75% (ref 90%) | trail 10 m (ref 83 m)" (campo novo 'freio_txt'; o texto antigo do feedback permanece).
- Teste novo: teste_v18_coach_pedais (40 verificacoes); contagens de janelas dos testes atualizadas (v1.8: 9 janelas; LMU: 35). Sem homologacao em jogo real: depende de a referencia ter freio/acelerador gravados; referencias antigas sem acelerador mostram so o freio.

## 1.8.0 build ao (corretiva - auditoria da build an)
- P1: a importacao nao substitui mais o cronograma.json quando NENHUMA serie do arquivo novo tem horario calculavel (todas com cadencia desconhecida); mensagem especifica e o cronograma bom e o backup ficam intactos. Cronograma parcialmente conhecido continua aceito.
- P2: carregar() valida a estrutura (series, semanas, datas, cadencias): serie malformada e descartada, cadencia fora do formato vira 'desconhecida', JSON sem nenhuma serie valida e rejeitado com mensagem; proximas/sem_horario/listar_series/dica_vazio nao levantam excecao com dados malformados.
- Testes: teste_v18_cronograma_importar 74 verificacoes (P1: 4, P2: 12 novas). Calculos ja auditados inalterados.

## 1.8.0 build an (icone WolfxRacing na barra de tarefas + horarios do cronograma no fuso do Windows)
- Cronograma: os horarios (painel, previa, janela de horario) seguem por padrao o fuso horario do Windows, inclusive horario de verao, em vez de um numero fixo (-3). A tela de filtros mostra o fuso em uso (UTC-03:00) e tem a opcao de fuso fixo manual. Configuracoes antigas passam a usar o fuso do Windows.
- O botao do overlay na barra de tarefas do Windows aparecia com o icone do Python. Agora o programa define identificador proprio (WolfxRacing.Overlay.iRacing / .LMU) e usa wolfxracing.ico como icone de todas as janelas (sem o .ico, cai na logo/icone padrao).
- Teste novo: teste_v18_icone. Sem homologacao em jogo real; o resultado visual depende do Windows (reinicie o overlay; se o icone antigo ficar, desafixe o botao da barra e abra de novo).

## 1.8.0 build am (Classificacao: bandeira quadriculada ao encerrar a sessao)
- Classificacao (iRacing): com a sessao encerrada (SessionState >= 5 ou bit de quadriculada em SessionFlags) aparece uma bandeira quadriculada ondulada, suave, no fundo da tabela, e um quadradinho quadriculado ao lado de cada piloto que recebeu a bandeira (CarIdxSessionFlags). A coluna so ocupa largura depois do encerramento.
- Duas opcoes na Central (Classificacao): "Bandeira quadriculada no fundo ao encerrar a sessao" e "Bandeira quadriculada ao lado de quem terminou" (ligadas por padrao). A previa da Central mostra a bandeira para voce ver o efeito.
- O log registra uma linha de calibracao quando a sessao encerra (estado, flags, carros com bandeira) para validar no simulador. LMU nao alterado (usa outra classificacao).
- Teste novo: teste_v18_classif_bandeira (22 verificacoes). Sem homologacao em jogo real.

## 1.8.0 build al (cronograma: importar novo PDF e filtros ao vivo)
- Importar novo cronograma dentro do overlay: botao "Importar novo cronograma (PDF)..." na tela de filtros, na Central (painel Calendario) e no menu da bandeja; tambem aceita arrastar o PDF/.txt para a tela de filtros. So troca o cronograma.json se o novo for valido; o anterior fica em cronograma_anterior.json; avisa series marcadas que nao existem mais e cronograma ja encerrado. Se faltar o leitor de PDF (pypdf), oferece instalar com um clique.
- Tela de filtros AO VIVO: cada marcacao atualiza na hora o painel Calendario, a previa da Central e uma previa dentro da propria tela (proximas corridas, contagem regressiva, linhas laranja = em aviso). Sem resultado, a tela diz qual filtro mais restringe. Botoes Marcar as visiveis / Desmarcar todas e contador de series. Cancelar desfaz tudo; Salvar grava.
- Previa da Central (painel Calendario) deixa de mostrar corridas de exemplo fixas quando o aviso do cronograma esta ligado: mostra o cronograma real com os filtros.
- Filtros mais rapidos (pre-filtro por serie/pista/carro/classe antes de gerar horarios; cache de datas); o servico confere o cronograma.json a cada 2 s (antes 20 s).
- Teste novo: teste_v18_cronograma_importar. Sem homologacao em jogo real.

## 1.8.0 build ak (corretiva - auditoria da build aj)
- importar_cronograma: 'GMT/UTC' deixa de desviar cadencias horarias para o parser semanal; horarios semanais preservam os minutos (19:30); tabelas que atravessam a quebra de pagina nao perdem mais as semanas seguintes (+249 semanas); nova classe_serie (secao do PDF) usada no filtro de classe.
- ov_cronograma: cadencia de 120 min sem paridade gera 84/semana (horas pares); horarios semanais aceitam [dia,hora] ou [dia,hora,minuto].
- Impactos: o log de cada impacto sai so com o evento final (apos refino e janela do incidente), numerado (#n); troca de sessao fecha os pendentes e nao gera '#0'. Limiares inalterados.
- Testes: teste_v18_cronograma 58 verificacoes (sem 'or True'); teste_v18_danos 24.

## 1.8.0 build aj (alertas piscantes na Telemetria)
- Fundo do grafico pisca: laranja com o limitador de pit, amarelo com o ABS atuando, azul com o TC atuando (prioridade: limitador, ABS, TC). Sem grafico, pisca o fundo do painel.
- Barra do freio pisca com o ABS atuando e a do acelerador com o TC atuando (so com o pedal pressionado).
- Tres opcoes na Central (Telemetria) para ligar/desligar cada alerta. Teste: teste_v18_alertas (16 verificacoes).

## 1.8.0 build ai
- Central: botao "Cronograma do iRacing: filtros e avisos" dentro do painel Calendario de corridas (antes so no menu avancado da bandeja).

## 1.8.0 build ah (novo - cronograma de corridas do iRacing)
- ov_cronograma.py / ov_cronograma_ui.py: cronograma a partir do PDF Season Schedule (cronograma.json), filtros por serie, pista, carro, classe e janela de horario, aviso visual no painel Calendario.
- importar_cronograma.py + atualizar_cronograma.bat: converte o PDF de cada temporada. 141 de 162 series com horario automatico; as demais sem aviso.
- Menu da bandeja (iRacing): Cronograma de corridas: filtros e avisos...
- Testes: teste_v18_cronograma (35 verificacoes). Sem homologacao em jogo real.

## 1.8.0 build ag (corretiva - deteccao de impactos do iRacing)
- Novo gatilho por salto de aceleracao (>= 2,5 g entre amostras com pico >= 2 g): pega batidas que ficavam abaixo de 6 g; frenagem forte nao dispara.
- Refino de 0,25 s: o pico real corrige zona e g do impacto.
- Incidente sem pico mensuravel agora conta no total e vai para o log.
- Testes: teste_v18_danos 14 verificacoes.

## 1.8.0 build af (corretiva - painel de Danos do iRacing)
- Contato leve (4x/2x) passa a marcar zona a partir de 1 g de pico (antes 2 g); saida de pista segue em 2 g.
- Tempo de reparo que sobe confirma o dano: eleva a severidade da zona recente ou cria evento "dano" (local indefinido).
- Reparo opcional entra na limpeza das marcas; rotulo "Local indefinido" no lugar de "Fora da pista" para contatos sem direcao.
- Cada impacto e gravado no overlay_log.txt (zona, tipo, g, reparo, incidentes) para diagnostico.
- Novo teste teste_v18_danos.py (10 verificacoes). Sem homologacao em jogo real.

## [1.8.2] - 2026-11-22

### Resumo da versao 1.8.2 (build ba)
- Corretiva da auditoria da v1.8.1: fontes dentro do EXE com verificacao de aplicacao; recorte da Classificacao Foto; atualizador LMU com trava ativa/orfa e gerado do mesmo commit; publicacao amarrada ao commit da tag.

### O que foi validado de fato (build ba)
- GitHub Actions, PR #3, cabeca `94d05fd` (commit testado = merge `d40906e`), Windows Server 2025, Python 3.12, PySide6/Qt 6.12, Qt nativo (`windows`): **57/57 suites com codigo de saida 0**; idioma da maquina Qt en_US.
- Windows com `offscreen` (informativo, nao bloqueia): 53/57 suites; falham `teste_v170_estados_vazios`, `teste_v170_previa_opcoes`, `teste_v18_integracao` (as tres ja eram conhecidas e dependem de fontes do motor offscreen) e `teste_v182_classif_foto_recorte` (2 verificacoes, so no offscreen do Windows: medidas de fonte de reserva; nao reproduzidas no Qt nativo do Windows nem no Linux). Nao sao defeitos confirmados do produto, mas ficam registradas como pendencia de investigacao.
- Linux, offscreen: todas as suites com codigo de saida 0.
- EXE congelado (Linux, PyInstaller) extraido em pasta limpa: `--verificar-fontes` = 0, Orbitron/Michroma/Bungee carregadas e aplicadas; controle sem a pasta de fontes = falha, como esperado. A verificacao com o EXE de Windows roda no workflow de publicacao.
- **Simulador real: NAO homologado. Stream Deck real: NAO testado.**

## [1.8.1] - 2026-11-22

### Resumo da versao 1.8.1 (builds as a az)
- **Telemetria:** ordem dos itens personalizavel (as); posicao e estilo livres de cada item em todos os paineis com itens (at, au); correcoes de auditoria (av a ay).
- **Fontes:** negrito e italico visiveis em todos os temas, inclusive Vidro/Bahnschrift e Orbitron; sonda de negrito otimizada (az).
- **Classificacao LMU:** cabecalho corrigido nos layouts foto e classico (ay, az); pacote COMPLETO de atualizacao com verificacao de manifesto e reversao (ay, az).
- **Executor de testes:** rodar_todos_os_testes.py com codigo de saida por suite e --plataforma windows|offscreen; testes de cronograma portateis para o Windows (az).
- Validado com testes automaticos e dados simulados; a homologacao em simulador real segue pendente. Detalhes por build acima.

### O que foi validado de fato (build az)
- **Windows Server 2025, Python 3.12.10, PySide6/Qt 6.12.0, Qt nativo (`windows`), via GitHub Actions: 55/55 suites com codigo de saida 0.**
- Linux, Python 3.13, Qt 6.12.0, `offscreen`: 55/55 suites com codigo de saida 0.
- Windows com `offscreen` (informativo): falham verificacoes de largura/corte que dependem de fontes (Central, "opcoes cabem na coluna"; JanelaConsumo); nao ocorrem no Qt nativo nem no Linux.
- Comparacao visual com a referencia congelada da build au: sem diferenca na aparencia padrao.
- Dados sinteticos e modo demo. **Simulador real: NAO homologado**; a validacao com o jogo e com o Stream Deck reais segue pendente.
- Atualizacao completa do LMU (anexo `WolfxRacing_LMU_1.8.1_buildAZ_atualizacao_completa.zip`): migracao ae -> az validada em copia isolada (17/17) e instalada em um PC real com backup; a reversao sob bloqueio de arquivo foi SIMULADA (injecao de erro), nao testada com bloqueio real do Windows.

## [1.8.0] - 2026-11-17

### Resumo da versão 1.8.0 (build ar)
- **Multi-idioma:** Português (Brasil), English, Español, Deutsch, Français e Italiano; automático pelo idioma do Windows, troca em *Central > Aparência e sistema* e no menu da bandeja (Central e menus pedem reinício; texto sem tradução aparece em português).
- **Coach:** % de freio, trail braking e % do acelerador, com a janela **Pedais do Coach** (posição livre e centralizável).
- **Novas janelas:** Mapa de vazão, Eficiência por marcha, Destino do combustível, Digiflag, Alerta de ultrapassagem, Calendário de corridas (importa o PDF *Season Schedule* do iRacing), Energia híbrida (Boost), Tempo da sessão; Calculadora de FOV; Danos estimados; modo daltônico; temas da Central; atalhos e Stream Deck para as janelas novas.
- Validado com testes automáticos e dados simulados; a validação em corrida real e no Stream Deck real segue em andamento. Detalhes por build abaixo.

### Build ae (Stream Deck dos painéis da 1.8 — produto 1.8.0)
- **Mesmo código funcional do build ad (auditado)**; a única mudança de código são os atalhos globais novos (`ov_nucleo.py`, `ov_atalhos_lmu.py`) e o `BUILD`.
- **Atalhos para os 8 painéis novos:** Mapa de vazão, Eficiência por marcha, Destino do combustível, Digiflag, Alerta de ultrapassagem, Calendário de corridas, Energia híbrida (Boost) e Tempo da sessão. iRacing: **Ctrl+F13..F20**; LMU: **Shift+F13..F20** (mapas separados, sem colisão entre si nem com os atalhos antigos, que mantêm o mesmo código). Cada atalho faz o mesmo que o item do menu da bandeja.
- **Perfis do Stream Deck XL (iRacing e LMU):** a pasta *Telas novas* ganhou os 8 botões (12 botões no total), com 8 ícones novos no padrão visual da biblioteca (original). Gerador atualizado (`icones_v18.py`; variáveis `WOLFX_BASE` e `WOLFX_PERFIL` para gerar o perfil com a pasta de instalação do seu PC).
- Testes: novo `teste_v18_atalhos.py` (mapa, alvos e config, perfil do Stream Deck com as teclas certas); contagens de atalhos dos testes antigos atualizadas (iRacing 39, LMU 35). Sem homologação com o Stream Deck real.

### Build ad (correções da auditoria do build ac — produto 1.8.0)
- **P1 — Calculadora de FOV (`ov_fov.py`):** passa a recusar, com mensagem em português, geometrias fisicamente impossíveis (FOV total do triplo ≥ 360°, largura ou profundidade não positivas), curvatura negativa, zero, NaN ou infinita (inclusive na lateral) e proporção personalizada inválida entregue diretamente como par (zero, negativa, NaN, infinita, texto, tamanho errado). Casos da auditoria: triplo 49" 32:9 a 15 cm (antes 455,7° e largura −89,5 cm), curvatura −1000 mm, curvatura NaN e proporção 16:0 agora são recusados; a Central mostra o aviso e não registra erro.
- **Modelo do triplo explicitado e unificado:** as três telas ficam à mesma distância do olho, a lateral girada e virada para o olho; cada tela é um arco (plana = raio infinito) e as bordas de tela curva ficam mais perto (flecha). Bordas, cantos traseiros, largura X, profundidade Y e medidas de fita vêm do mesmo desenho (antes a lateral curva usava a largura plana e ignorava a flecha). A largura X agora inclui o fundo das laterais giradas. Avisos para FOV total acima de 270° e laterais atrás da linha dos olhos. A moldura continua sendo uma aproximação do vão angular (documentada).
- **P2 — Versão:** `VERSAO_PRODUTO` passa de 1.7.0 para **1.8.0** (cabeçalho do log, backup, resumo de suporte, LMU, LEIA-ME, receitas EXE); `BUILD` = ad. Nenhuma publicação.
- Testes: `teste_v18_fov.py` de 60 para 102 verificações (reproduções da auditoria, curvatura/proporção inválidas, coerência FOV × ângulo × X × Y × fita, varredura de 1500 entradas estranhas). A varredura achou e corrigiu um `TypeError` ao receber lista na proporção. Sem funcionalidades novas e sem homologação em jogo real.

### Build ac (visual da Central e Destino do combustível — produto 1.8.0)
- **Central, aba Painéis, em novo visual (futurista/app moderno):** filtros por categoria em pílulas com contagem no topo (a lista lateral saiu), cartões de vidro escuro com prévia em "poço" luminoso, pílula de estado *LIGADO/DESLIGADO* com chave, categoria, título e descrição em até 2 linhas e botão *Personalizar ›*. Cartão ligado destaca na cor do tema; até 4 colunas conforme a largura. Menu lateral, busca e botões com cantos arredondados e realce em degradê. Referências visuais (RaceLab etc.) são apenas inspiração de estilo; nenhum recurso gráfico de terceiros foi copiado.
- **Destino do combustível redesenhado:** tabela por faixa de acelerador (A FUNDO/ALTO/MÉDIO/BAIXO/SOLTO) × faixas de RPM, % por célula (`<1%`), célula atual com caixa branca, barra A FUNDO/PARCIAL/SOLTO, frase de maior zona e stint no cabeçalho. Opção `destino_litros` mantida. Medição pelo nível do tanque, sem novo algoritmo.
- Testes: novos casos de `_r_destino` (célula atual, parcela parcial, RPM máximo) e da galeria/Destino (filtros, busca, colunas, estados do painel). Sem homologação no jogo real.

### Build ab (nova ferramenta na Central — produto 1.8.0)
- **Calculadora de FOV** (item *Calculadora de FOV* no menu lateral da Central), em português e igual nos dois jogos: informe distância até a tela, diagonal, proporção (16:9, 21:9, 32:9 ou personalizada), tela curva (raio) e, no triplo, a moldura por emenda (negativa = telas sobrepostas) e laterais diferentes da central. Mostra FOV vertical e horizontal, FOV total e ângulo das laterais no triplo, largura (X) e profundidade (Y) ocupadas, medidas com fita para conferir o ângulo, o que digitar em cada jogo (iRacing: horizontal; Le Mans Ultimate: vertical, conforme a referência da calculadora de Dan Suzuki) e o ajuste fino de ±10 %. Exemplos prontos; as últimas entradas ficam salvas (`fov_calc`).
- Não altera arquivos do jogo (a configuração automática por upload de arquivos da calculadora original não foi reproduzida). Cálculo próprio (`ov_fov.py`): tela plana ou curva, triplo com laterais à mesma distância dos olhos; a profundidade usa 8 cm de espessura de painel e a largura soma cerca de 2 cm de estrutura.
- Testes: novo `teste_v18_fov.py` (60 verificações: referências calculadas à mão, curva, triplo, moldura, entradas inválidas, 300 casos aleatórios, página da Central e persistência).

### Build aa (redesenho visual das janelas Mapa de vazão e Eficiência por marcha — produto 1.8.0)
Entrega **separada do build z** (que ficou restrito às duas correções da auditoria). Só apresentação: nenhum número já auditado mudou.
- **Mapa de vazão:** janela mais larga (440 px); cabeçalho no topo (AGORA, ÚLTIMA VOLTA, MÉDIA e, quando o jogo informar, MAPA do motor); eixo de RPM no alto com a coluna atual em caixa branca e barra de zona de RPM alto; linhas de acelerador de 0 a 100 % com a linha atual em caixa branca; números em todas as células (agora **ligado por padrão**; continua desligável); escala azul → ciano → verde → amarelo → laranja → vermelho; **trilha** da posição nos últimos 4 s; legenda com mínimo e máximo. Novo elemento do painel: *Trilha da posição recente*.
- **Eficiência por marcha:** cabeçalho com o consumo de agora (L/100 km, só a acelerador pleno e > 20 km/h) e selo da marcha engatada; grade com valor na faixa de RPM mais alta de cada marcha; **marcador do RPM atual** na marcha engatada; **linha tracejada "MÁX x.xk"** com o RPM máximo observado na marcha engatada e marca do máximo em cada marcha (não é detecção de ponto de troca); eixo de RPM; coluna PARCELA; legenda inferior ("só acelerador pleno · RPM · menor é melhor"). Novos elementos do painel: *Marcador do RPM atual* e *Legenda inferior*.
- Dados novos (só apresentação): `vazao.trilha`, `vazao.rpm`, `vazao.mapa_motor`, `marcha.agora_l100`, `marcha.rpm`. O campo MAPA aparece apenas se o jogo informar `mapa_motor` (nenhum dos dois adaptadores informa hoje).
- Compatibilidade: chaves de configuração e elementos anteriores continuam valendo.
- Testes: lógica 152 → 165; integração + 23 verificações do redesenho.

### Build z (corretiva sobre o build y, produto 1.8.0)
- **Eficiência por marcha — média geral:** passa a ser consumo total ÷ distância total das amostras elegíveis × 100 (antes: média simples das células, que dava o mesmo peso a células com tempos de observação muito diferentes). Células individuais, melhor/pior e filtros (acelerador pleno, > 20 km/h, dados válidos, pausas) inalterados.
- **Eficiência por marcha — "RPM máximo observado":** o antigo "RPM de troca" era apenas o maior RPM visto em cada marcha a acelerador pleno (sem detecção de troca). Renomeado na interface, nos dados (`rpm_max`) e na documentação; nenhum algoritmo novo. A chave interna da opção (`troca`) foi mantida: configurações anteriores continuam valendo.
- Testes: `teste_v18_logica.py` 139 → 152; `teste_v18_integracao.py` ganhou 14 verificações dos estados visuais da janela.

### Build y (corretiva sobre o build x, produto 1.8.0)
- **Mapa de vazao e Eficiencia por marcha**: as medias das celulas passam a ser **ponderadas pelo tempo valido** (antes: media por numero de amostras, distorcida por taxa de aquisicao variavel). Intervalos longos/pausas, dados invalidos e fora da pista continuam fora da media.
- **Alerta de ultrapassagem**: o rastreamento usa o **identificador estavel do carro** (`id`/`idx`); sem ele, numero + classe + nome. Troca de identidade no mesmo id reinicia o historico. Carros com o mesmo numero em classes diferentes nao se misturam mais. O adaptador do LMU passa a entregar o `id`.
- **Hibrido**: "ultima volta" (`ult_carga`/`ult_deploy`) passa a ser a **ultima leitura valida da volta que terminou**, nao a do instante da troca; leituras invalidas preservam o ultimo valor valido.
- Testes: `teste_v18_logica.py` de 93 para 139 verificacoes. Configuracoes anteriores continuam compativeis (nenhuma chave nova).

Oito janelas novas, modo daltônico e temas de vidro para a Central, tudo personalizável no painel (cada janela tem *ELEMENTOS* liga/desliga, opções próprias e prévia ao vivo) e nos dois jogos. As janelas novas nascem **desligadas**: ligue em *Central > Painéis* ou no menu da bandeja. Passou por todas as suítes automáticas; **a conferência no jogo real (variáveis do sistema híbrido, relativo/classificação do LMU) ainda precisa ser feita** (ver o roteiro no relatório).

- **Novo - Mapa de vazão:** mapa de calor do consumo instantâneo (L/h) por faixa de RPM x abertura do acelerador (11 x 10 células), com marcador da posição atual, legenda e consumo agora/última volta/média. Preenche conforme você dirige; célula sem amostra fica apagada. Opção: números nas células.
- **Novo - Eficiência por marcha:** L/100 km a acelerador pleno (>= 90 %) em cada marcha e faixa de RPM, com a parcela do tempo e o RPM máximo observado de cada marcha; só conta acima de 20 km/h. Opção: destacar a marcha engatada.
- **Novo - Destino do combustível:** quanto do combustível medido saiu a fundo/alto/médio/baixo/solto e em que faixa de RPM, litros do stint (zera ao sair dos boxes) e onde mais gasta. Opção: mostrar em litros. É gasto medido pelo nível do tanque, nunca uma estimativa de economia.
- **Novo - Digiflag:** painel colorido com a bandeira em vigor (usa a detecção da janela Bandeiras; quadriculada e azul têm desenho próprio). Opção: pulsar nas bandeiras de atenção.
- **Novo - Alerta de ultrapassagem:** até 4 carros que se aproximam por trás (diferença em segundos, velocidade de aproximação, classe); só aparece com alerta (opção), segura 2 s para não piscar, ignora carros nos boxes e de outra volta (opções) e pode ser limitado a outras classes; limite de 3 s ou 5 s. No iRacing usa a lista do Relativo; no LMU a diferença é distância/velocidade (calculada).
- **Novo - Calendário de corridas:** próximas corridas com horário, classe, contagem regressiva e fechamento do registro, lidas de um arquivo seu (`calendario_corridas.csv`, modelo em `calendario_exemplo.csv`). **Por que um arquivo:** o iRacing só entrega a agenda de corridas oficiais com login na sua conta (API autenticada), e o overlay não pede nem guarda senha nem acessa a internet. Relê o arquivo sozinho quando ele muda.
- **Novo - Energia híbrida (Boost):** carga da bateria, uso do deploy na volta e valores da volta anterior; avisa (pisca) abaixo de 15 %. LMU: bateria do hipercarro (`mBatteryChargeFraction`, estado do motor elétrico); iRacing: carros GTP/LMDh (`EnergyERSBatteryPct`, `EnergyMGU_KLapDeployPct`, `PowerMGU_K`). Só mostra dado quando o jogo informa; carro sem híbrido mostra o aviso. **Os nomes das variáveis do iRacing ainda precisam ser conferidos num carro híbrido real.**
- **Novo - Tempo da sessão:** tempo (ou voltas) restante com barra de progresso e percentual corrido; fica amarelo nos últimos 5 minutos. Opção: sempre em h:mm:ss.
- **Novo - Modo daltônico** (Central > Aparência): Deuteranopia, Protanopia e Tritanopia trocam as cores de bom/ruim (verde/vermelho) das janelas por pares que o tipo escolhido distingue (deuteranopia/protanopia: verde -> azul, vermelho -> laranja, aviso -> amarelo claro; tritanopia: azul/ciano -> violeta, amarelo -> laranja). Cinzas, branco e preto não mudam. É uma troca de paleta, **não uma simulação clínica**; se algum par continuar difícil, avise qual.
- **Novo - Aparência da Central:** Clássico escuro e três temas de vidro (Grafite, Gelo, Âmbar), escolhidos em *Central > Aparência*; só mudam a janela de configurações.
- **Corrigido - Elementos liga/desliga não eram lembrados ao reiniciar:** as escolhas de *ELEMENTOS* (Relativo, Clima, Pneus, Voltas, Coach, Consumo, Curvas, Setores, Tendência) eram gravadas, mas descartadas ao carregar o config; só o Delta Trace e a Classificação persistiam. Agora todas persistem (teste de ida e volta).
- **Teste:** `teste_v18_logica.py` (logica pura: faixas, litros integrados, L/100 km, ultrapassagem, híbrido, sessão, calendário, paleta) e `teste_v18_integracao.py` (janelas em todos os estados, config e persistência, Central, temas, modo daltônico pixel a pixel, extras do LMU e do iRacing); `teste_v170_previa_opcoes.py` passou a cobrir as janelas novas.

## [1.7.0] - 2026-11-04

Versão grande: **Coach ao vivo**, camada de dados por jogo e novidades de uso. Passou por todas as suítes automáticas em pista
simulada; **a calibração em sessão real ainda precisa ser confirmada** (ver `docs/COACH.md`).

- **Corrigido (build w) - Prévia ao vivo da Central parada:** a prévia trabalhava numa cópia do config feita ao criar; interruptores de ação (Telemetria: barra horizontal e gráfico; Voltas: cálculo de combustível; Relativo: projeção; Classificação: todas as classes etc.) mudavam só a janela real. Agora a Central sincroniza o config real com a prévia antes de cada desenho e reaplica o layout só quando algo mudou. **Corrigido (build w) - Delta Trace na Central:** os dois botões de layout lado a lado passavam da coluna e cortavam os interruptores; agora ficam empilhados. **Novo (build w, pedido do mantenedor) - Elementos liga/desliga em Relativo** (cabeçalho, rodapé, posição, número, pneu, licença, iRating, distância), **Clima** (cada cartão: pista, ar, neblina, chuva, vento; a janela encolhe) **e Pneus** (temperatura total, zonas, vida, detalhes, rodapé). **Pneus:** a temperatura total do pneu ganhou destaque (fonte 10 → 16). Limitação conhecida: as colunas do Relativo e os itens dos cartões de Pneus ocultos não compactam na horizontal. Novo teste_v170_previa_opcoes.py (95 verificações: toda opção de todo painel muda a prévia; opções cabem na coluna; reproduz os defeitos da build v). Entrega build w.
- **Corrigido (build v) - A Central não abria (build t e u):** `montar_central` tentava gravar `modo_previa` em `Telemetria._demo`, que no iRacing é um *método* (no LMU é um objeto); resultado: `AttributeError` e nenhuma Central ("o painel não abre"). Os testes passavam porque nenhum montava a Central com a telemetria de demonstração real. Corrigido e coberto por `teste_v170_central_real.py` (iRacing e LMU; reproduz o defeito).
- **Corrigido (build v, auditoria independente da build u) - Estados de espera cortados:** com seções desligadas, a mensagem de espera de Coach, Tendência, Curvas e Consumo ("Aguardando…", "Dirija uma volta limpa…") podia ficar cortada ou fora da janela (ex.: Coach só com o título = 30 px de altura). Agora a janela nunca fica abaixo de 100 px de altura base quando há seção desligada e a mensagem se posiciona logo abaixo do título; com tudo ligado o desenho é idêntico. O Coach deixa de desenhar o divisor da borda de baixo quando nada vem depois. Novo `teste_v170_estados_vazios.py` (240 verificações: 7 painéis x todas as combinações de elementos x 50/100/150/200 % x dados/sem dados/desconectado/gravando; nada cortado, mensagem sem sobrepor o título, cada seção inteira e no lugar certo, config antiga/corrompida, alternância dados/sem dados).
- **Alterado (build v) - Delta Trace:** a linha azul passa a se chamar **ritmo ideal estimado** (na janela e na Central), deixando claro que é a soma dos melhores trechos e não uma volta realmente feita; só o ganho estimado é mostrado, nunca um tempo de volta. Novo `teste_v170_ritmo_ideal.py` (propriedades com voltas aleatórias, troca de referência, voltas incompletas/inválidas/com buracos, rótulo).
- **Teste (build v) - Ciclo real do Coach:** `teste_v170_coach_ciclo_real.py` (iRacing: `Telemetria.ler()` completo com pyirsdk simulado) e `teste_v170_coach_ciclo_lmu.py` (LMU: `TelemetriaLMU.ler()` com o jogo simulado) confirmam que o Coach recebe dados, fecha volta e grava a referência pelo ciclo real. O teste do iRacing reproduz o defeito da build r; no LMU a ordem do ciclo nunca teve o defeito (o Coach já era alimentado depois do tempo da volta), a leitura direta apenas remove a dependência de ordem. Sem novas funcionalidades. Produto 1.7.0 **não publicado**. Entrega **build v**.
- **Novo (build u) - Elementos liga/desliga em todos os painéis com seções:** Curvas, Setores, Coach, Consumo, Tendência e Voltas ganharam, em *Central > painel > ELEMENTOS*, interruptores por elemento (título, cartão, lista, rodapé, números, gráfico, legenda etc.) com prévia ao vivo. Ao ocultar uma seção, a janela encolhe a altura dela e as seções de baixo sobem (framework único em `JanelaBase`: `ELEMENTOS`, `SECOES`, `visivel`, `_abre/_fecha`); tudo ligado = desenho idêntico ao da build t. Delta Trace migrou para o mesmo framework (`delta_trace_elementos` mantido). Voltas: colunas ocultas sem compactação horizontal (limitação conhecida). Tendência: a seção da legenda ficou rente ao rodapé (12 px) para a janela encolher sem sobra. Teste novo `teste_v170_elementos.py` (95 verificações; desenho padrão, encolhimento, deslocamento e persistência). Produto 1.7.0 **não publicado**. Entrega **build u**.
- **Corrigido (build t) - Prévias da Central:** as prévias dos painéis que só aparecem com um evento ficavam em branco (Luz do ABS sempre; Luz do TC, Auxiliar de sessão e Retorno à pista boa parte do tempo). A prévia agora mostra sempre o painel ativo. A prévia do painel aberto atualiza ~8 vezes por segundo, e falhas de desenho da prévia passam a ir para o `overlay_log.txt` (antes eram engolidas). Teste novo `teste_v170_previas.py` varre 15 min de demonstração em todos os painéis.
- **Novo - Delta Trace (build s):** linha azul de *ritmo ideal estimado* no gráfico (renomeada na build v): a soma dos seus melhores trechos da sessão contra a referência, com o ganho possível escrito embaixo (ex.: *azul: melhor ritmo (-0,32s)*). Aparece a partir da 2ª volta válida; liga/desliga na Central em *Elementos* ("Ritmo ideal estimado").
- **Corrigido (build s, teste real) - Coach:** a janela ficava em *"Dirija uma volta limpa"* e nunca gravava a referência. O Coach era alimentado antes de `tempo_volta` e `ultima_volta` serem montados e recebia sempre vazio; agora lê o tempo direto do jogo (iRacing e LMU). Teste novo `teste_v170_coach_real.py` reproduz o defeito e cobre a correção.
- **Classificação:** suporte ao número de voltas do pneu dentro da bolinha (aparece quando o jogo fornece o dado; no LMU segue com a letra por ora).
- **Corrigido (auditoria independente, build j) - Melhor por curva:** chicanes não se fundem mais (uma zona de cada volta por curva, mesmo tipo, distância circular, raio 60 m calibrado com .ibt reais); voltas diferentes com o mesmo tempo não são mais descartadas (identificador de volta); a dica descreve a diferença observada (`C4 | Melhor passagem: -0,15 s | Freada 12 m depois da referência`), sem causalidade, e só aparece acima do ruído do trecho.
- **Corrigido (auditoria) - Gravação:** histórico e referência própria são gravados em segundo plano (nada de disco na thread do Coach), descarregados ao encerrar; o cache das dicas acompanha o histórico.
- **Corrigido (auditoria) - Contagem 3-2-1:** usa a distância e a sua velocidade (a base da contagem é identificada); nunca negativa.
- **Corrigido (auditoria) - Importação:** CSV recusa volta sem início/fim, buracos, arquivo truncado e unidade absurda, e avisa extrapolação pequena; .ibt distingue validação completa/parcial e recusa volta de saída/largada, salto de posição, troca de sessão e linha de largada deslocada; referência e histórico corrompidos são ignorados.
- **Medição:** o log registra `coach_desempenho` (p50/p95/p99 por atualização). Novo teste: `teste_v170_auditoria.py`.
- **Corrigido (auditoria, 2ª rodada, build j) - Gravação:** cada gravação em segundo plano leva uma **versão** e um snapshot antigo nunca sobrescreve um mais novo, mesmo agendado fora de ordem (a 1ª rodada podia perder voltas); falha de gravação tenta 3 vezes, vai para o log (`Coach: nao consegui gravar...`), não é perdida em silêncio e é regravada ao encerrar; `descarregar()` respeita o prazo e o encerramento grava o que sobrou. Duas voltas distintas e muito parecidas de origens diferentes passam a ser mantidas (critério de máximo **e** média). Versão padronizada: produto **1.7.0**, entrega **build j** (aparece no cabeçalho do log); os rótulos internos de sub-versão foram removidos.
- **Corrigido (auditoria da build q, build r):** (P1) **Delta Trace, blocos por curva:** o posicionamento não garantia que o último bloco ficasse dentro do gráfico (com 20 curvas, 4 blocos passavam do limite direito, até 108 px). Agora uma função pura (`layout_blocos`) posiciona todos os blocos dentro da faixa, sem sobreposição, adapta a largura mínima quando há muitas curvas e mantém a largura proporcional ao tempo sempre que couber (se não couber, só o excesso acima do mínimo é reduzido, na mesma proporção); nada invade o painel do mapa; com blocos estreitos o valor numérico some e fica só a cor. Testado com 5, 10, 15, 20, 25 e 30 curvas. (P2) **Curva sobre a linha de chegada:** o analisador de curvas do Coach limita as zonas a 0..N-1 e, portanto, não gera uma zona circular (uma curva que atravessa a linha sai como duas zonas), mas `zonas_de_curvas()` descartava o formato início > fim. Agora a zona circular é mantida como uma só e blocos, destaque da curva, delta parcial e desenho da pista a tratam (delta = trecho antes da linha + trecho depois; parcial depois da linha = sem valor, pois o início ficou na volta anterior). Consumo, histórico, persistência, Coach e atalhos não foram alterados (`ov_coach.py` idêntico ao da build n). **Novo (pedido do Adriano):** opção de **layout estilo RaceLab** no Delta Trace (Central > Delta Trace > Layout do painel): número grande no centro e barra horizontal a partir do zero (verde para a esquerda = ganhando, vermelho para a direita = perdendo); blocos por curva e mapa continuam; o layout em gráfico segue como padrão (`delta_trace_layout`). **Personalização no mesmo esquema da Classificação** (Central > Delta Trace > Elementos): liga/desliga título e referência, delta grande, gráfico/barra, volta anterior tracejada, blocos por curva, número da curva e desenho da pista, com prévia ao vivo; a janela encolhe junto (tudo ligado = 710 x 200, como antes; `delta_trace_elementos`). Não há reordenação de elementos nesta build. Número da curva com 2 ou 3 dígitos agora cabe sem cobrir o delta. Entrega **build r**.
- **Novo (build q) - Delta Trace redesenhado, atalhos e Stream Deck das telas novas:** (1) **Delta Trace**: gráfico de área preenchida (verde = ganhando, vermelho = perdendo, volta anterior tracejada) no **eixo do tempo**, delta grande no cabeçalho, uma faixa de **blocos por curva** abaixo do gráfico (largura proporcional ao tempo gasto na curva, cor = ganho/perda; as curvas ainda não feitas ficam apagadas) e, à direita, o **número da curva** (a atual ou a próxima), o delta parcial dela e o **desenho da pista no estilo do Minimapa** (contorno claro + miolo escuro, largada/chegada, seu carro): o trecho já percorrido nesta volta fica **verde onde você ganhou tempo e vermelho onde perdeu**, e a curva em foco ganha moldura. Sem o Mapa aprendido (ou no LMU sem traçado) o painel mostra só o número. As curvas vêm do analisador do Coach (nenhum dado novo é gravado). (2) **Ponto cego retirado** (redundante com o Radar). (3) **Atalhos globais** para Consumo, Delta Trace e Janela de curvas (Alt+F21, Alt+F22 e Alt+F23, tabela `ATALHOS` do núcleo; sem colisão com as demais). (4) **Stream Deck**: nova pasta **Telas novas** (Consumo, Delta Trace, Curvas) com 4 ícones novos; no perfil do iRacing o botão da pasta do overlay foi para a pasta Suporte. Perfil regerado e validado estruturalmente (zip, imagens, atalhos); **não foi testado no aplicativo Stream Deck real**. Texto do painel Consumo: "trechos de maior consumo (indicativo, não é economia)". Entrega **build q**.
- **Corrigido (auditoria da build o, build p):** (P1) **Delta Trace:** quando uma nova melhor volta substituía a referência, o gráfico cinza da volta anterior continuava calculado contra a referência antiga (ex.: ref. 100 s, nova melhor 90 s: mostrava −10 s em vez de zero). Agora a classe guarda os **tempos brutos** de cada volta e todo delta é recalculado contra a referência vigente (atual e anterior). (P2) **Burn Zones:** o rótulo passou a *Trechos de maior consumo (indicativo, não é economia)*, sem sugerir ganho de combustível não calculado; o algoritmo de zonas não mudou. (P2) **Robustez, com justificativa medida:** o acúmulo de consumo descartava as leituras em que o nível subia e, com ruído do sensor, superestimava o gasto (ruído de 0,002 L: +61 %); passou a acumular com sinal (viés ~0) e o limiar de reabastecimento subiu de 0,02 para 0,05 L (com ruído de 0,005 L a volta era descartada); o fluxo L/h usa a média das pontas da janela. Delta Trace: pontos pulados por taxa de leitura baixa (até 10) são interpolados (referência válida até 1 Hz; antes falhava a 2 Hz) e o relógio da volta que zera um pouco antes/depois da posição (comum no LMU) é ressincronizado sem descartar a volta; reinício no meio da volta descarta a volta. Novo teste `teste_v170_onda1_robustez.py` (65 verificações: regressão de referências sucessivamente melhores, ruído/resolução, taxas variáveis, 200 pontos, voltas rápidas/lentas, troca de referência, interrupções). Sem novas janelas; Coach, curvas, classificação e persistência inalterados. Entrega **build p** (produto 1.7.0, não publicado).
- **Novo (build o) - Onda 1 de painéis** (produto 1.7.0, não publicado): (1) **Consumo / Burn Zones + Fuel Flow** (painel `Consumo`, categoria Carro): divide a volta em 24 trechos e mostra onde o carro gasta mais combustível, o fluxo instantâneo em L/h, o consumo médio e da última volta por volta e a tendência; só conta volta completa e limpa (sem box, reabastecimento, saída de pista ou salto de posição) e precisa de 3 voltas limpas para marcar as zonas. É **indicativo**: não promete economia em litros. (2) **Delta Trace** (painel `Delta Trace`, Pilotagem): gráfico do delta ao longo da volta contra a melhor volta limpa da sessão (ganho sobe/verde, perda desce/vermelho, volta anterior em cinza). Consumo e Delta Trace funcionam nos dois jogos; nada é gravado em disco; Coach, curvas e persistência inalterados (`ov_coach.py` idêntico ao da build n). Novos arquivos: `ov_onda1.py`; novos testes: `teste_v170_onda1.py` (e `teste_v170_onda1_lmu.py` no LMU). O contrato de dados ganhou as chaves opcionais `consumo` e `delta_trace`. Entrega **build o**.
- **Corrigido (auditoria da build m, build n):** (1) Classificação sem dados com barra/títulos escondidos: a altura padrão encolhe o mesmo tanto do topo (mínimo 80 px; tudo visível = 170 px, como antes); (2) a Central registra no `overlay_log.txt` (gancho `registrar_erro`) a falha de `opcoes_mudaram()` em vez de engoli-la, sem interromper a Central; (3) `estresse_concorrencia.py` lê o argumento de rodadas antes de alterar `sys.argv`. Coach, telemetria, curvas e persistência inalterados. Entrega **build n** (produto 1.7.0, não publicado).
- **Novo (build m) - Classificação como no Kapps:** na Central, cada coluna ganhou setas ▲▼ para **mudar a ordem** (a largura de cada coluna acompanha; sem sobreposição) e o cabeçalho é personalizável: liga/desliga a barra superior, o tipo da sessão, volta, tempo, temperaturas, umidade, incidentes, clima, total de carros (N CARS) e a linha de títulos das colunas; a janela encolhe junto. Botões "Ordem original", "Mostrar todas as colunas" e "Mostrar todo o cabeçalho". Tudo aparece na hora na prévia ao vivo, em iRacing e LMU. Com tudo no padrão o desenho é idêntico ao da build l. Só interface (Coach inalterado). Entrega **build m** (produto 1.7.0).
- **Novo (build l) - Painel de configuração com prévia em tempo real:** em *Classificação*, liga/desliga cada coluna (posição, +/-, número, pneu, licença, iRating, marca, país, piloto fixo, gap, intervalo, melhor, última, pit, stint) e a janela se reajusta; em *Minimapa*, numeração da posição dentro de cada bolinha (na classe ou geral) e sua posição ao lado da seta; em *Telemetria*, imagem PNG própria no lugar do volante desenhado (enviar, girar com o volante, tamanho, voltar ao desenhado). Toda mudança aparece na hora na prévia ao vivo. Com tudo ligado, o desenho é pixel a pixel igual ao da build k. Só interface: Coach, curvas e constantes inalterados. Entrega **build l** (produto 1.7.0).
- **Corrigido (build l) - Encerramento do gravador:** uma exclusão (ou gravação) já retirada da fila pela thread gravadora, mas ainda não executada, podia ficar pendente se o encerramento terminasse nesse intervalo; `gravar_agora` agora assume esse trabalho em voo. Teste de regressão 7d-bis.
- **Corrigido (auditoria, 3ª rodada, build k) - Apagar histórico:** uma gravação já em andamento podia recriar o arquivo do histórico depois de "Apagar o histórico por curva". Agora a exclusão é entregue à mesma thread que grava e executada sob o lock de I/O, depois da gravação em curso e antes de qualquer snapshot novo; os snapshots invalidados ficam abaixo de um piso de versão e nunca são publicados. O pedido espera no máximo 1,5 s (nunca indefinidamente): se a gravação demorar, a exclusão fica agendada, com aviso no log. Exclusão que falha (arquivo em uso) é repetida e segura as novas gravações da pista até concluir. Produto **1.7.0**, entrega **build k**.
- **Novo - Melhor por curva (dica) e resumo da sessão** (mesmo núcleo do iRacing): dica em verde no painel do Coach e menu do Coach > *Resumo da sessão...*. A referência principal não muda.
- **Novo - Coach ao vivo** (painel `Coach`, iRacing e LMU): distância até a próxima freada, contagem 3-2-1-FREIE, marcha e velocidade-alvo no ápice, delta contra a referência e avaliação da curva anterior ("freou cedo ~14 m", "ápice -3 km/h"). A referência é a sua melhor volta limpa (gravada sozinha por pista e carro) ou uma volta importada.
- **Novo - Importar volta de referência (CSV):** importador tolerante (colunas, unidades e separadores variados), pasta de entrada, modo automático (usa a mais rápida entre a sua e a importada; volta de outro carro não passa à frente da sua)/própria/importada e apagar. Formato do Garage 61 **confirmado com CSV real** (Speed em m/s, LapDistPct, Brake/Throttle 0-1, Gear; sem coluna de tempo): o tempo da volta é lido do nome do arquivo exportado. O overlay não acessa a internet.
- **Novo - Referência a partir das suas telemetrias (.ibt, iRacing):** o Coach lê os arquivos de `Documents/iRacing/telemetry`, escolhe a melhor volta válida (completa, sem boxes e sem sair da pista) da mesma pista, carro e traçado e a usa como referência própria já na primeira volta da sessão (em segundo plano, uma vez por pista e carro; opção no menu). Também aceita importar um `.ibt` de outro piloto pelo menu.
- **Validado com telemetria real (5 arquivos do iRacing: BMW M4 GT3 em Fuji e Red Bull Ring, MX-5 em Okayama e Summit Point):** o delta ao vivo difere do tempo real de volta em média 0,007 a 0,026 s; as notas de freada ficam em perfeita/boa na grande maioria das curvas. Um falso "freou muito cedo" em curvas próximas (cauda da freada anterior contada como freada desta curva) foi corrigido.
- **Novo - Resumo de stint e ritmo-alvo:** aponta a curva em que mais se perde e mostra o alvo (média das 3 melhores voltas limpas), a diferença da última volta e quanto poupar de combustível por volta quando necessário.
- **Novo - Avisos por voz (opcional, desligado):** voz do Windows, no máximo uma frase a cada 2 s.
- **Novo - Opacidade por painel** (Central > painel > "Opacidade do fundo").
- **Novo - Backup e restauração da configuração** e **copiar resumo para suporte** (menu "Configuração: backup e suporte").
- **Novo - Amigos:** lista de nomes destacados em verde, com estrela, na Classificação e no Relativo.
- **Novo - Contrato de dados e adaptadores** (`ov_dados.py`, `docs/CONTRATO_DE_DADOS.md`): base da v2.0 (app único), sem mudar o que o piloto vê.
- **Novo - Coach considera a tirada de pé (sem freio):** além das zonas de freada, o Coach acha onde a referência tira o pé do acelerador sem frear (curvas rápidas), avisa com 3-2-1-**TIRE** e avalia ("tirou o pé cedo/tarde", "não tirou o pé"). Validado nas 5 telemetrias reais (Fuji 2, Okayama 2 e Summit Point 2 zonas de tirada; Red Bull Ring nenhuma).
- **Novo - A pasta de telemetria .ibt é relida durante a sessão** quando chega arquivo novo (checa a cada 2 minutos, só lê se mudou); a referência só troca se a nova volta for mais rápida.
- **Corrigido - Linha de entrada do pit:** só é aprendida entrando de verdade pela pista (acima de 36 km/h e até 1.500 m antes do box), nunca ao nascer no box. O arquivo passou a ser `pit_entradas_v2.json`. No LMU a janela já só aparece quando o jogo informa pedido de parada.
- Novos testes automáticos: `teste_v170_tirada.py`, `teste_v170_pasta.py`, `teste_v170.py`, `teste_v170_import.py`, `teste_v170_ritmo_voz.py`, `teste_v170_backup.py`, `teste_v170_amigos.py`, `teste_v170_ibt.py`.
- Itens adiados com medição (da revisão externa): emblemas fora da pintura, cache de fontes, seleção de linhas duplicada. Nenhum entrou sem número que o justifique.

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
