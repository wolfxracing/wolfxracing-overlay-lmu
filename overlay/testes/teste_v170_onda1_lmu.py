# -*- coding: utf-8 -*-
"""Onda 1 (build o) no LMU, pelo caminho completo: memoria falsa -> TelemetriaLMU.ler() -> Consumo / Delta Trace.
Cobre a ordem de montagem (tempo_volta/ultima_volta so existem depois de _montar_v12). NAO prova o LMU real."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teste_lmu as T                                   # noqa: E402
from teste_lmu import confere, grupo                    # noqa: E402


def volta(j, tel, rel, tempo=60.0, litros=2.0, hz=20):
    c, comp = j.carros[3], j.comprimento
    n = int(tempo * hz)
    j.inicio_volta = j.tempo_decorrido
    d = None
    for k in range(n):
        c.dist = (k / n) * comp
        rel.avancar(1.0 / hz); j.et += 1.0 / hz; j.tempo_decorrido += 1.0 / hz
        j.combustivel -= litros / n
        d = tel.ler()
    return d


def principal():
    grupo("Onda 1 no LMU - Consumo e Delta Trace pelo caminho real")
    T.preparar_modulo()
    j = T.cenario_corrida()
    j.carros[3].voltas = 1; j.carros[3].dist = 0.0
    tel, rel = T.telemetria(j)
    d = tel.ler()
    confere(d.get("consumo") is not None and d["consumo"]["estado"] == "sem_dados", "antes das voltas: consumo sem dados")
    confere(d.get("delta_trace") is not None and d["delta_trace"]["estado"] == "sem_ref", "antes das voltas: delta trace sem referencia")
    for k in range(5):
        j.carros[3].ultima = 60.0 + (0.3 if k == 0 else 0.0)
        volta(j, tel, rel)
        j.carros[3].dist = 0.01 * j.comprimento; rel.avancar(0.05); d = tel.ler()
    c = d["consumo"]
    confere(c["voltas"] >= 3 and c["estado"] == "ok", f"consumo mede voltas limpas ({c['voltas']}, {c['estado']})")
    confere(c["medio_lv"] is not None and 1.5 < c["medio_lv"] < 2.5, f"consumo medio ~2 L/volta ({c['medio_lv']})")
    t = d["delta_trace"]
    confere(t["estado"] == "ok" and t["voltas"] >= 1, f"delta trace tem referencia ({t['estado']}, {t['voltas']})")
    # volta pelo box nao conta
    antes = tel.vo_consumo.resumo()["voltas"]
    j.carros[3].box = True
    volta(j, tel, rel); j.carros[3].box = False
    j.carros[3].dist = 0.01 * j.comprimento; rel.avancar(0.05); tel.ler()
    confere(tel.vo_consumo.resumo()["voltas"] == antes, "volta nos boxes nao entra no consumo")
    # sessao nova zera
    j.sessao = 3; j.et += 5.0; rel.avancar(5.0); d = tel.ler()
    confere(d["consumo"]["voltas"] == 0 and d["delta_trace"]["estado"] == "sem_ref", "sessao nova zera consumo e delta trace")
    # janelas existem na base e no LMU (sem Ponto cego: o LMU nao tem ocupacao lateral)
    import overlay_iracing as b
    confere(hasattr(b, "JanelaConsumo") and hasattr(b, "JanelaDeltaTrace"), "janelas Consumo e Delta Trace disponiveis")


if __name__ == "__main__":
    try:
        principal()
    except Exception:
        import traceback
        T._falhas.append("excecao"); traceback.print_exc()
    print(f"\nResultado LMU Onda 1: {T._ok} verificacoes ok, {len(T._falhas)} falha(s).")
    for f in T._falhas:
        print(" -", f)
    sys.exit(1 if T._falhas else 0)
