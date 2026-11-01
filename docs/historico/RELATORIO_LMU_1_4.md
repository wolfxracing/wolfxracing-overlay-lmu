# Relatório LMU 1.4.0 — Perfil de Stream Deck XL "Overlay LMU"

## Resumo executivo
Criado o perfil **"Overlay LMU"** para o Stream Deck XL, no mesmo padrão visual e estrutural do perfil do iRacing ("Overlay iRacing"): página principal (12 janelas + controles + iniciar/fechar) e pasta **Suporte**, 33 botões com ícones novos de 144×144. Para o perfil funcionar, o overlay LMU ganhou **20 teclas globais próprias** (F13..F24), com combinações **diferentes** das do iRacing — os dois perfis convivem sem colisão. Overlay e perfil do iRacing **não foram alterados** (hash conferido). Bateria automática: **todas as verificações passaram** (inclui teste que lê o próprio `.streamDeckProfile` e confere cada botão contra o programa).

**Status:** gerado e testado em simulação. A importação no Stream Deck real e o efeito de cada botão com o jogo aberto **ainda não foram validados** (Teste 15 do roteiro).

## Análise objetiva
**O que existia:** o overlay LMU não registrava teclas globais (a tabela `ATALHOS` vive no núcleo do iRacing), portanto um perfil de Stream Deck não teria o que acionar.

**O que foi feito**
- `ov_atalhos_lmu.py` (novo): mapa `ATALHOS_LMU`, reaproveitando a maquinaria já homologada do iRacing (`AtalhoGlobal`, `EscutaTeclas`, `DespachanteTeclas`, `RegisterHotKey`) sem alterar o núcleo.
- `overlay_lmu.py` (v1.4.0): escuta das teclas, item de menu "Teclas de atalho para o Stream Deck" (liga/desliga, salvo), cada atalho chama o **mesmo item do menu da bandeja** que o clique do mouse já usava. Correção de bônus: a trava de instância única agora é liberada ao sair.
- `streamdeck_lmu/`: perfil, 33 ícones (PNG+SVG), variantes "desligada", prévias, geradores, mapa de comandos.

**Mapa de teclas (sem colisão com o iRacing)**
| Grupo | iRacing | LMU |
|---|---|---|
| Janelas | Ctrl+Alt+Shift+F13..F24 | **Ctrl+Shift+F13..F24** |
| Controles | Ctrl+Alt+F13..F22 | **Alt+Shift+F13..F20** |

**Layout da página principal (coluna,linha)**
- Linha 0: Telemetria, Voltas, Classificação, Clima, Combustível, Força G, Energia, Pneus e freios
- Linha 1: Danos, Alertas, Stints, Tendência, Todas as classes, Manter no topo, Tamanho padrão, Zerar pico de G
- Linha 2: Economia de CPU, Aparecer sozinho, Travar posição | Modo demo, Abrir log, Pasta do overlay
- Linha 3: Iniciar overlay, Fechar overlay, Forçar fechamento | Suporte (7,3)
- Suporte: Voltar, Lista de atalhos, Guia rápido, Roteiro, Rodar testes, Rodar diagnóstico, Ver diagnóstico

**Diferenças para o iRacing:** sem botões de perfil Treino/Classificação/Corrida (o LMU não tem esse recurso) e sem Relativo/Mapa/Radar/Setores/Limpar impactos (não existem no LMU).

**Riscos e limites**
- O Stream Deck não lê o estado do overlay: o botão alterna, mas o ícone não muda sozinho (igual ao iRacing).
- Formato do perfil copiado do perfil exportado pelo próprio usuário; importação real não validada.
- Se outro programa/plugin usar a mesma combinação, o overlay avisa na bandeja e no log; os demais atalhos seguem funcionando.
- As teclas F13..F24 não existem em teclados comuns: não digitam no jogo.

## Recomendação final
Importar o perfil, rodar o **Teste 15** do roteiro com o jogo em Window/Borderless e, se tudo bater, adotar como padrão. Se algum botão falhar, enviar o `overlay_log_lmu.txt` (linhas "atalhos globais").

## Próximos passos
1. Stream Deck > Importar > `streamdeck_lmu\Overlay LMU.streamDeckProfile`.
2. Fechar e reabrir o overlay LMU (v1.4.0) para registrar as teclas.
3. Executar o Teste 15 e anotar PASSOU / FALHOU / DÚVIDA por botão.
4. Opcional: associar o perfil ao executável do LMU nas configurações do Stream Deck (troca automática de perfil).
5. Pendências da v1.3 continuam: zonas de dano esquerda/traseira-esquerda, alertas em corrida com IA, diagnóstico do vento.
