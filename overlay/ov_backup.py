# -*- coding: utf-8 -*-
"""
Backup e restauracao da configuracao + resumo para suporte (v1.7) - logica pura, sem Qt.

  exportar(config, jogo, versao)  -> texto JSON com a configuracao (arquivo .json que o piloto guarda onde quiser)
  importar(texto, padrao, jogo)   -> (config_nova, avisos): SO aceita chaves que o programa conhece, com o tipo certo
  resumo_suporte(...)             -> texto curto para colar em um pedido de ajuda (sem caminhos de pastas pessoais)
"""
import json
import math
import platform
import sys
import time

FORMATO = "wolfxracing-config"
LIMITES_ESCALA = (0.3, 4.0)


class ErroBackup(Exception):
    """Mensagem curta em portugues para mostrar ao piloto."""


def exportar(config, jogo, versao):
    return json.dumps({"formato": FORMATO, "jogo": jogo, "versao": versao, "criado": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "config": config}, indent=1, ensure_ascii=False)


def _tipo_compat(padrao, valor):
    if padrao is None:                                      # ex.: escala por eixo (None = acompanha a escala unica)
        return valor is None or (isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor))
    if isinstance(padrao, bool):
        return isinstance(valor, bool)
    if isinstance(padrao, (int, float)):
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    if isinstance(padrao, str):
        return isinstance(valor, str)
    if isinstance(padrao, dict):
        return isinstance(valor, dict)
    if isinstance(padrao, list):
        return isinstance(valor, list)
    return True


def importar(texto, padrao, jogo=None):
    """Devolve (config_nova, avisos). config_nova = padrao + as chaves validas do arquivo. Levanta ErroBackup."""
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        raise ErroBackup("o arquivo nao e um JSON valido")
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO or not isinstance(dados.get("config"), dict):
        raise ErroBackup("este arquivo nao e um backup de configuracao do WolfxRacing")
    avisos = []
    if jogo and dados.get("jogo") and dados["jogo"] != jogo:
        avisos.append(f"o backup e de outro jogo ({dados['jogo']}); as posicoes podem nao servir")
    novo = json.loads(json.dumps(padrao))                   # copia profunda
    ignoradas = 0
    for chave, valor in dados["config"].items():
        if chave not in padrao or not _tipo_compat(padrao[chave], valor):
            ignoradas += 1
            continue
        if (chave.startswith("escala") and isinstance(valor, (int, float)) and not isinstance(valor, bool)):
            valor = min(LIMITES_ESCALA[1], max(LIMITES_ESCALA[0], float(valor)))
        novo[chave] = valor
    if ignoradas:
        avisos.append(f"{ignoradas} item(ns) desconhecido(s) ou invalido(s) foram ignorados")
    return novo, avisos


def resumo_suporte(versao, jogo, config, linhas_log=(), extras=None, max_linhas=40):
    """Texto para colar em um pedido de ajuda. Sem caminhos pessoais e sem dados de conta."""
    ligadas = sorted(k[len("mostrar_"):] for k, v in config.items() if k.startswith("mostrar_") and v is True)
    partes = [f"WolfxRacing Overlay {versao} ({jogo})", f"Python {sys.version.split()[0]} | {platform.platform()}",
              f"Perfil: {config.get('perfil_ativo')} ({config.get('perfil_modo')}) | travado: {config.get('travado')}",
              "Paineis ligados: " + (", ".join(ligadas) if ligadas else "nenhum")]
    for k, v in (extras or {}).items():
        partes.append(f"{k}: {v}")
    linhas = [l.rstrip() for l in list(linhas_log)[-max_linhas:]]
    if linhas:
        partes += ["", f"--- ultimas {len(linhas)} linhas do log ---"] + linhas
    return "\n".join(partes)
