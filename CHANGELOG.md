# Histórico de versões

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e [SemVer](https://semver.org/lang/pt-BR/).

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
