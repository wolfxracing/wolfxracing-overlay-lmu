# Contrato de dados (v1.7)

Todas as janelas do overlay leem **um único dicionário** (o *snapshot*), montado a cada ciclo. Cada jogo tem um **adaptador**
que entrega esse dicionário. Este documento descreve as chaves, para que um novo jogo (ou a v2.0, com os dois jogos num só
aplicativo) só precise de um adaptador que cumpra o contrato.

- **Obrigatória:** sempre presente, com o tipo indicado.
- **Opcional:** pode ser `None` (o jogo não fornece ou ainda não há dado). Quando presente, tem o tipo indicado.
- As chaves `lmu_*` só existem no LMU; no iRacing ficam `None`/ausentes.
- Código: `overlay/ov_dados.py` (`CONTRATO`, `validar_snapshot`, `criar_adaptador`). O teste `testes/teste_v170.py` valida o
  snapshot de demonstração dos dois jogos contra este contrato.

## Adaptadores

```python
import ov_dados
adaptador = ov_dados.criar_adaptador("iracing")   # ou "lmu"
dados = adaptador.ler(validar=True)               # dicionário do contrato
adaptador.problemas_ultimo                        # lista de violações do contrato (vazia = ok)
```

O adaptador **envolve** as classes de leitura já testadas (`Telemetria` e `TelemetriaLMU`); não muda os dados.

## Chaves

| Chave | Tipo | Obrigatoria | Descricao |
|---|---|---|---|
| `conectado` | bool | sim | ha dados do jogo |
| `no_carro` | bool | sim | o piloto esta dentro do carro, no mundo do jogo |
| `replay` | bool | sim | o jogo esta em replay |
| `tipo_sessao` | txt | nao | CORRIDA / QUALIFICACAO / TREINO... |
| `marcha` | int | sim | marcha atual (0 = neutro, -1 = re) |
| `velocidade` | num | sim | km/h |
| `rpm` | num | sim | rotacao |
| `rpm_max` | num | sim | rotacao maxima do carro |
| `acelerador` | num | sim | 0..1 |
| `freio` | num | sim | 0..1 |
| `embreagem` | num | sim | 0..1 (1 = pisada) |
| `volante` | num | sim | graus (positivo = para a esquerda) |
| `volta` | int | sim | volta atual |
| `tempo_volta` | num | nao | s, volta em andamento |
| `ultima_volta` | num | nao | s |
| `melhor_volta` | num | nao | s |
| `delta` | num | sim | s, negativo = mais rapido que a melhor volta |
| `combustivel` | num | sim | litros |
| `forca_g` | dict | nao | G lateral/longitudinal |
| `clima` | dict | nao | pista, ar, vento |
| `pneus` | dict | nao | temperatura/desgaste por roda |
| `danos` | dict | nao | reparos e impactos |
| `relativo` | dict | nao | carros proximos |
| `classificacao` | dict | nao | classes e linhas |
| `mapa` | dict | nao | minimapa |
| `radar` | dict | nao | radar |
| `curvas` | dict | nao | v1.4.0: velocidade minima por curva |
| `consumo` | dict | nao | v1.7.0 build o: consumo por trecho (Burn Zones) e fluxo (L/h) |
| `delta_trace` | dict | nao | v1.7.0 build o: delta ao longo da volta; build q: `ref_tempos` (tempos brutos da referencia) e `curvas` (zonas das curvas) |
| `bandeira` | dict | nao | v1.5.0 |
| `trafego` | dict | nao | v1.5.0 |
| `tendencia` | dict | nao | v1.6.0: ritmo |
| `pit` | dict | nao | v1.6.0 |
| `coach` | dict | nao | v1.7.0: orientacao ao vivo (referencia por distancia) |
| `abs` | bool | nao | ABS atuando |
| `abs_nivel` | num | nao | ajuste do ABS, se o carro tiver |
| `tc` | dict | nao | ajuste do controle de tracao |
| `bias` | num | nao | balanco de freio dianteiro, se ajustavel |
| `luz_tc` | dict | nao | v1.2.0: TC atuando |
| `pedais_cru` | dict | nao | v1.2.0: pedais sem a calibracao do carro |
| `retorno` | dict | nao | v1.2.0: retorno a pista |
| `estrategia` | dict | nao | v1.2.0: chuva x seco |
| `auxiliar` | dict | nao | v1.5.0: etapa e tempo restante da sessao |
| `contato` | dict | nao | v1.6.0: ultimo carro tocado |
| `delta_ok` | bool | nao | o delta e confiavel |
| `delta_fonte` | txt | nao | 'overlay' (calculado aqui) ou 'sim' (do jogo) |
| `consumo_volta` | num | nao | litros por volta |
| `voltas_restantes` | num | nao | voltas de combustivel restantes |
| `calc_combustivel` | dict | nao | calculadora de combustivel |
| `painel_combustivel` | dict | nao | janela de pit e autonomia |
| `projecao` | dict | nao | projecao de iRating/SR (so iRacing) |
| `setores` | dict | nao | setores da volta |
| `lmu_alertas` | dict | nao | alertas na pista |
| `lmu_danos` | dict | nao | danos por peca |
| `lmu_energia` | dict | nao | energia virtual |
| `lmu_pneus` | dict | nao | pneus e freios |
| `lmu_stints` | dict | nao | historico de stints |
| `lmu_tendencia` | dict | nao | tendencia do LMU |

## Chave `coach` (v1.7)

Saída de `Coach.resumo()` (ver `ov_coach.py`): `estado` (`gravando`/`ok`/`sem_contexto`), `fonte` (`propria`/`importada`),
`proxima` (zona de frenagem à frente: `n`, `dist_m`, `fase`, `contagem` `3`/`2`/`1`/`FREIE`, `marcha`, `vel_apice`...),
`delta`, `feedback` (avaliação da última curva), `resumo_volta`, `stint`, `ritmo`, `ritmo_texto`, `aviso`.
