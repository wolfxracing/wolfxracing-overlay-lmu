# Histórico de versões

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e [SemVer](https://semver.org/lang/pt-BR/).

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
