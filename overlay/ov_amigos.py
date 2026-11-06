# -*- coding: utf-8 -*-
"""Lista de amigos (v1.7): nomes destacados na classificacao e no relativo. Logica pura, sem Qt.
Regra de casamento: todas as palavras do nome do amigo precisam aparecer no nome do piloto (sem diferenciar maiusculas nem
acentos). 'Ana' casa com 'Ana Souza' mas NAO com 'Diana'; 'Joao Silva' casa com 'Joao Pedro Silva'."""
import re
import unicodedata


def _palavras(txt):
    txt = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode().lower()
    return tuple(re.findall(r"[a-z0-9]+", txt))


def preparar(entradas):
    """Lista (ou texto, uma entrada por linha ou separada por virgula/ponto e virgula) -> tupla de tuplas de palavras."""
    if isinstance(entradas, str):
        entradas = re.split(r"[\n;,]+", entradas)
    out = []
    for e in entradas or []:
        p = _palavras(e)
        if p and p not in out:
            out.append(p)
    return tuple(out[:200])


def eh_amigo(nome, preparada):
    if not preparada:
        return False
    palavras = set(_palavras(nome))
    return any(all(w in palavras for w in amigo) for amigo in preparada)
