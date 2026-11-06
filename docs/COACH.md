# Coach ao vivo (v1.7)

O Coach diz, durante a volta, **onde frear, qual marcha usar e que velocidade ter no ápice**, comparando você com uma
**volta de referência**. Funciona no iRacing e no LMU, com os mesmos dados que o overlay já lê (velocidade, pedais, marcha,
posição e tempo da volta).

## Como funciona
1. **Referência.** Uma volta guardada em 1000 trechos da pista, alinhada pela **distância** (não pelo tempo). Pode ser a sua
   melhor volta limpa (o overlay grava sozinho, por pista e carro) ou uma volta **importada** em CSV.
2. **Zonas de frenagem.** O overlay acha, na referência, cada trecho em que houve freada firme e guarda: ponto de freada,
   ápice, velocidade no ápice e marcha no ápice.
3. **Ao vivo.** Distância até o próximo ponto de freada, contagem **3-2-1-FREIE**, marcha e velocidade-alvo, delta contra a
   referência.
4. **Depois da curva.** Compara a sua freada (metros mais cedo/tarde), a velocidade no ápice e a marcha.
5. **Depois da volta.** Resumo; se a volta for limpa e mais rápida, ela vira a nova referência própria.
   O resumo do **stint** aponta a curva em que você mais perde.
6. **Ritmo.** Alvo = média das 3 melhores voltas limpas do stint; mostra a diferença da última volta e, se faltar combustível
   para chegar ao fim sem parar, quanto poupar por volta.

## Menu (bandeja) > "Coach: referência e importação"
- **Modo:** automático (a **mais rápida** entre a sua e a importada; uma importada de outro carro nunca passa à frente da sua), só a sua, ou só a importada.
- **Avisos por voz** (voz do Windows): desligado por padrão. Anuncia a curva e a marcha, avalia freadas com problema e avisa
  combustível. No máximo uma frase a cada 2 s.
- **Importar volta de referência (CSV)...**, **Importar o CSV mais novo da pasta de entrada**, **Abrir a pasta de entrada**
  (`referencias/entrada`) e **Apagar a volta importada desta pista e carro**.

## Suas telemetrias do iRacing (.ibt)
O iRacing grava a telemetria de cada sessão em `Documents\iRacing\telemetry` (arquivos `.ibt`). Ao entrar em uma pista, o Coach procura ali, **em segundo plano e uma vez por pista e carro**, a melhor volta válida do **mesmo carro, pista e traçado** (comprimento dentro de 1,5%) e a usa como referência própria, sem você precisar gravar uma volta antes. Volta válida = completa, sem passar pelos boxes e sem sair da pista. Menu: **Carregar sozinho a minha melhor volta das telemetrias gravadas** (liga/desliga) e **Procurar agora**. O `.ibt` de outro piloto também pode ser importado pelo menu (Importar volta de referência), desde que seja da mesma pista.
O LMU não grava `.ibt`; no LMU a referência é gravada pelo próprio overlay.

## Importar uma volta de outro piloto (CSV)
O importador é **tolerante**: reconhece vários nomes de coluna, unidades (m/s, km/h, mph), escalas (0-1 ou 0-100) e separadores
(vírgula, ponto e vírgula, tabulação; vírgula decimal). Colunas:

| Campo | Nomes aceitos (exemplos) | Obrigatória |
|---|---|---|
| Posição na volta | `LapDistPct` (0-1 ou 0-100) **ou** `LapDist` (metros) | sim |
| Velocidade | `Speed`, `Speed (km/h)`, `velocidade` | sim |
| Freio | `Brake`, `freio` | sim |
| Marcha | `Gear`, `marcha` | sim |
| Acelerador | `Throttle`, `acelerador` | não |
| Tempo | `LapCurrentLapTime`, `time`, `tempo` | não (sem ele, é calculado pela velocidade) |

Antes de importar, **entre no carro e passe pela linha de chegada uma vez**: o overlay precisa saber a pista, o carro e o
comprimento da volta. Volta de outro traçado (comprimento muito diferente) é recusada; de outro carro, aceita com aviso.

> **Garage 61:** o formato exato do CSV do Garage 61 **ainda não foi confirmado com um arquivo real**. Se a importação
> recusar um arquivo, a mensagem diz o que faltou; envie o cabeçalho do CSV (as primeiras linhas) para ajustarmos.
> O overlay **não** acessa a internet nem a API do Garage 61. Respeite os termos de uso do serviço e mantenha o crédito ao
> piloto de origem (o nome do arquivo fica guardado na referência).

## Limites
- Não existe ponto de freada "ideal" calculado: a referência é a de um piloto real e **depende do carro e do acerto dele**.
  Use volta importada só se o carro e o acerto forem comparáveis.
- A calibração (antecipação da contagem, ruído) só se confirma **em sessão real**. Os testes automáticos usam uma pista
  simulada.
- Convenção do overlay: `~` indica estimativa.
- Confira a política do iRacing/LMU para ferramentas que leem telemetria antes de usar em competições oficiais.


## CSV do Garage 61 (confirmado)
No site: abra o evento, ao lado da volta clique na seta e em **Export to CSV**. Salve na pasta de referências sem renomear: o nome traz o tempo da volta (ex.: `... - 01.22.572 - ID.csv`), pois o CSV não tem coluna de tempo. Colunas: Speed (m/s), LapDistPct, Brake e Throttle (0-1), Gear, RPM, SteeringWheelAngle (rad), Lat/Lon. Não há API de exportação em massa e o Garage 61 restringe o uso da API (docs oficiais); a importação é manual.

## Tirada de pé (sem freio)
Em curva rápida o piloto muitas vezes só **tira o pé** do acelerador. O Coach procura essas zonas na referência: o acelerador vinha embaixo, cai abaixo de 35% sem freio por pelo menos 10 m e volta (tiradas coladas numa freada pertencem a ela). A janela mostra **TIRE** (amarelo) na contagem 3-2-1 e **TIRANDO** durante a tirada; depois da curva avalia: *tirada perfeita/boa*, *tirou o pé cedo/tarde (~N m)*, *não tirou o pé* ou *freou onde bastava tirar o pé*. As curvas são numeradas juntas (C1, C2...) com as de freada. Limitação: "não tirou o pé" pode ser até mais rápido, então pesa pouco no resumo da volta.

## Melhor por curva e resumo da sessão (1.7.0, revisto na auditoria, build j)
- **Histórico:** cada volta válida sua (ao vivo e das telemetrias .ibt, no iRacing) é guardada por pista e carro (até 40 voltas, pasta `referencias/historico`). Cada volta tem um **identificador** (origem, sessão, número, tempo e impressão digital do relógio): duas voltas diferentes com o mesmo tempo são mantidas; a mesma volta vinda do ao vivo e do .ibt não duplica. Voltas acima de 107% do seu melhor tempo não contam. Históricos antigos (sem identificador) continuam valendo; voltas corrompidas são ignoradas ao carregar. Menu do Coach: *Apagar o histórico por curva desta pista e carro*.
- **Gravação em segundo plano:** nada é gravado em disco na thread que atualiza o Coach/painéis. O histórico e a referência própria vão para uma fila de gravação (o snapshot mais novo vence, gravação atômica com arquivo temporário + `os.replace`) e são descarregados ao encerrar o overlay. Cada snapshot tem **versão monotônica**: um mais antigo que chega atrasado é descartado. Se a gravação falhar, o overlay tenta 3 vezes, avisa no log e regrava ao encerrar (`coach_gravacao` no log mostra gravações, falhas e descartes). **Apagar o histórico** é serializado com o gravador (build k): a exclusão roda na thread de gravação, depois da gravação em curso e antes de qualquer snapshot novo; o que foi invalidado fica abaixo de um piso de versão e nunca é publicado, então um snapshot antigo não recria o arquivo apagado. A thread do overlay espera no máximo 1,5 s; se a gravação demorar, a exclusão continua agendada (aviso no log) e é concluída ao fim dela ou no encerramento.
- **Curvas:** as zonas de freada e de tirada de pé de cada volta são agrupadas pelo ápice (distância **circular**, raio 60 m), **só do mesmo tipo** e **no máximo uma zona de cada volta por curva** (chicanes ficam separadas). O trecho cronometrado vai de 50 m antes do evento a 80 m depois do ápice e pode atravessar a linha de chegada.
- **Dica ao vivo (só descreve; não afirma causa):** `C4 | Melhor passagem: -0,15 s | Freada 12 m depois da referência`. Aparece quando há ao menos 3 passagens, a melhor foi mais rápida que a da referência por mais que 0,03 s **e** mais que o desvio-padrão do tempo daquele trecho entre as suas voltas (diferenças dentro do ruído não geram dica), e o evento difere em 6 m ou o ápice em 3 km/h. Freada nunca é comparada com tirada de pé. Diferença no ponto de freada não é a causa do ganho. **A referência principal nunca é trocada.**
- **Contagem 3-2-1:** usa a **distância** até o ponto e a **sua velocidade atual** (`contagem_base = distancia`); sem velocidade confiável (< 25 km/h) cai no relógio da referência (`referencia`), que não é previsão para você. Nunca negativa; trata a virada de volta.
- **Resumo da sessão** (menu do Coach): precisa de 3 voltas válidas da sessão. Mostra as curvas em que mais perdeu tempo (tempo do **trecho**, média da sessão contra a sua melhor passagem), a variação do ponto do evento e do ápice, quantas voltas foram usadas e a **cobertura da pista** pelos trechos analisados. A *volta ideal* é **estimativa** (soma das melhores passagens nesses trechos).
- **Limites:** curvas sem zona detectada em ao menos 2 voltas não entram. Não é limite físico: é o melhor que você já fez ali, no mesmo carro. Telemetria .ibt: só entram voltas com os canais de prova (boxes e pista) presentes; volta de saída/largada, salto de posição, troca de sessão e linha de largada deslocada em relação ao zero de `LapDistPct` são recusadas.
- **Medição:** o log registra `coach_desempenho` (p50/p95/p99 do `atualizar`); meta p95 ≤ 2 ms, p99 ≤ 5 ms.
