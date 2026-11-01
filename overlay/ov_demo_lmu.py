# -*- coding: utf-8 -*-
"""
Dados SIMULADOS das janelas novas do LMU, so para o modo demonstracao (testar_demo_lmu.bat) e para as imagens de
previa. Passam pelas MESMAS funcoes de calculo do overlay real (painel de energia, alertas, historico de stints);
so os numeros de entrada sao inventados. Nada disto e usado com o jogo aberto.
"""
import math
import time

import ov_alertas_lmu as alertas
import ov_classif_lmu as classif
import ov_estrategia_lmu as estr
import ov_lmu as lmu


def historico_demo():
    """Corrida simulada: 3 stints (M, M, H), 9 + 9 + 6 voltas, paradas nos boxes entre eles."""
    h = estr.HistoricoStints()
    chave = "demo"
    ve, comb, vida, volta, melhor, tempos = 100.0, 90.0, 1.0, 0, None, 0
    h.atualizar(chave, 0, False, ve, comb, vida, "M", None, None, 31.0)
    for si, (n_voltas, comp) in enumerate(((9, "M"), (9, "M"), (6, "H"))):
        for k in range(n_voltas):
            volta += 1
            ve -= 4.2 + 0.04 * k
            comb -= 2.4
            vida -= 0.026 + 0.001 * k
            ultima = 215.0 + 0.14 * k + 0.35 * math.sin(volta * 1.7) + (0.2 if si else 0.0)
            melhor = ultima if melhor is None else min(melhor, ultima)
            h.atualizar(chave, volta, False, ve, comb, vida, comp, ultima, melhor, 31.0 + 0.4 * volta / 4.0)
        if si < 2:                                           # volta de entrada nos boxes, reabastecimento e saida
            h.atualizar(chave, volta, True, ve, comb, vida, comp, None, melhor, 38.0)
            volta += 1
            h.atualizar(chave, volta, True, ve, comb, vida, comp, 262.0, melhor, 38.0)
            ve, comb, vida = 100.0, 90.0, 1.0
            proximo = "M" if si == 0 else "H"
            h.atualizar(chave, volta, True, ve, comb, vida, proximo, 262.0, melhor, 38.0)
            h.atualizar(chave, volta, False, ve, comb, vida, proximo, 262.0, melhor, 38.0)
    return h, melhor


def _carro(eu, lugar, classe, numero, dist, vel_ms, box=False, pit_estado=0, penalidades=0, bandeira=0, pit_dist=150.0):
    return {"id": lugar, "piloto": f"Piloto {lugar}", "veiculo": f"Carro #{numero}", "eu": eu, "lugar": lugar,
            "classe": lmu.classe_do_carro(classe), "numero": str(numero), "marca": "", "nome": "", "voltas": 10,
            "dist": dist, "ultima": 215.0, "melhor": 214.0, "box": box, "paradas": 0, "penalidades": penalidades,
            "combustivel": 128, "tbn": 1.0, "lbn": 0, "tbl": 1.0, "lbl": 0, "quali": lugar, "final": 0, "vel": vel_ms,
            "pit_estado": pit_estado, "pit_dist": pit_dist, "bandeira": bandeira}


# (lugar geral, classe, numero, piloto, quali - a quali real e recalculada por classe) - carro 24 (LMP2) e o do jogador
_GRID_DEMO = ((1, "Hypercar", 7, "A. Silva", 1), (2, "Hypercar", 51, "B. Costa", 3), (3, "Hypercar", 8, "C. Lima", 2),
              (4, "LMP2", 22, "D. Rocha", 4), (5, "Hypercar", 50, "E. Dias", 4), (6, "LMP2", 24, "VOCE", 6),
              (7, "LMGT3", 88, "F. Alves", 7), (8, "Hypercar", 35, "G. Melo", 5), (9, "LMP2", 28, "H. Pires", 5),
              (10, "LMGT3", 27, "I. Nunes", 8), (11, "LMP2", 43, "J. Reis", 6), (12, "LMGT3", 46, "K. Faria", 9),
              (13, "LMGT3", 78, "L. Souza", 10), (14, "LMGT3", 21, "M. Prado", 11))


def classificacao_demo(t=0.0):
    """Classificacao simulada pelo MESMO calculo do overlay real (ov_classif_lmu.montar), com carros inventados."""
    hist = classif.HistoricoVoltas()
    carros = []
    for lugar, cl, num, piloto, quali in _GRID_DEMO:
        base_t = {"Hypercar": 207.0, "LMP2": 214.0, "LMGT3": 226.0}[cl] + 0.35 * lugar
        c = _carro(piloto == "VOCE", lugar, cl, num, 3600.0 - 190.0 * lugar, 60.0)
        c.update(piloto=piloto, nome=piloto, veiculo=f"{cl} #{num}", voltas=10 if lugar < 12 else 9, ultima=base_t + 0.4,
                 melhor=base_t, tbn=1.2 + 0.35 * lugar, quali=quali, paradas=1 if lugar > 4 else 0,
                 combustivel=int(210 - 9 * lugar), box=(lugar == 14), penalidades=1 if lugar == 9 else 0)
        carros.append(c)
    por_classe = {}                                          # qualificacao sem repeticao dentro da classe
    for c in carros:
        por_classe.setdefault(c["classe"]["rotulo"], []).append(c)
    for membros in por_classe.values():
        for i, c in enumerate(sorted(membros, key=lambda c: int(c["lugar"])), start=1):
            c["quali"] = i
        if len(membros) > 2:
            membros[1]["quali"], membros[2]["quali"] = membros[2]["quali"], membros[1]["quali"]
    sessao = {"chave": "demo", "decorrido": 3723.0 + t, "total": 21600.0, "restante": 21600.0 - 3723.0 - t,
              "voltas_total": None, "pista": 31.0, "ar": 24.0}
    for v in range(3, 10):                                   # historico de voltas para a coluna de media
        for c in carros:
            c["voltas"] = v
            c["ultima"] = c["melhor"] + 0.3 * ((v * 7 + int(c["numero"])) % 5) / 4.0
            hist.atualizar(sessao["chave"], [c])
    for c in carros:
        c["voltas"] = 10 if int(c["lugar"]) < 12 else 9
        c["ultima"] = c["melhor"] + 0.4
    hist.atualizar(sessao["chave"], carros)
    return classif.montar(carros, 5000.0, "CORRIDA", hist, sessao, volta=11)


class DemoExtraLMU:
    """Entrega, a cada ciclo, as chaves das janelas novas (lmu_energia, lmu_pneus, lmu_danos, lmu_alertas, lmu_stints,
    lmu_tendencia) com valores simulados."""

    TROCA_CENARIO_S = 5.0

    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio
        self._t0 = relogio()
        self._hist, self._melhor = historico_demo()
        self._classif = classificacao_demo(0.0)
        self._alertas = alertas.AlertasLMU()
        self._alertas.limite_pit = 80.0

    def ler(self):
        t = self._relogio() - self._t0
        return {"classificacao": self._classificacao(t), "lmu_energia": self._energia(t), "lmu_pneus": self._pneus(t), "lmu_danos": self._danos(),
                "lmu_alertas": self._alertas_demo(t), "lmu_stints": {"stints": self._hist.resumo(self._melhor)},
                "lmu_tendencia": self._hist.tendencia(self._melhor)}

    def _classificacao(self, t):
        c = self._classif
        if c is not None:
            c["sessao"]["decorrido"] = 3723.0 + t
        return c

    @staticmethod
    def _energia(t):
        fase = int(t // 20) % 2
        ve = 61.0 - 0.02 * (t % 20)
        comb = 41.0 - 0.012 * (t % 20)
        return estr.painel_energia(ve, 4.3, comb, 90.0, 2.45, 12 if fase == 0 else 24, 19, 1.0)

    @staticmethod
    def _pneus(t):
        base_t = {"FL": 92.0, "FR": 99.0, "RL": 84.0, "RR": 88.0}
        vidas = {"FL": 78.0, "FR": 72.0, "RL": 81.0, "RR": 80.0}
        rodas = []
        for i, r in enumerate(lmu.RODAS):
            rodas.append({"roda": r, "temp": base_t[r] + 2.0 * math.sin(t * 0.6 + i), "pressao": 205.0 + 1.5 * math.sin(t * 0.4 + i),
                          "vida": vidas[r], "freio": 520.0 + 90.0 * math.sin(t * 0.9 + i), "otima": 90.0,
                          "composto": "M", "composto_nome": "Medium", "furado": False, "solta": False})
        return {"rodas": rodas, "oleo": 108.0, "agua": 92.0}

    @staticmethod
    def _danos():
        return {"zonas": [0, 1, 0, 0, 0, 0, 2, 1], "solta": False, "superaquecendo": False,
                "furados": [False] * 4, "rodas_soltas": [False] * 4, "impacto_desde": 214.0, "impacto_forca": 1850.0, "impacto_lado": "frente-esquerda"}

    def _alertas_demo(self, t):
        cenario = int(t // self.TROCA_CENARIO_S) % 4
        eu = _carro(True, 3, "LMP2", 24, 2000.0, 55.0)
        rapido = _carro(False, 1, "Hypercar", 7, 1650.0, 70.0)
        lento = _carro(False, 4, "LMGT3", 88, 2240.0, 14.0)
        bandeiras = {"fase": 5, "fcy": False, "fcy_estado": "", "parada": False, "amarelas_setor": []}
        limitador = {"ativo": False, "vel": 55.0 * 3.6, "nos_boxes": False}
        carros = [eu, rapido]
        if cenario == 0:
            bandeiras.update(fcy=True, fase=6, fcy_estado="retomada")
            eu["penalidades"] = 1
        elif cenario == 1:
            bandeiras["amarelas_setor"] = [1]
            carros = [eu, lento]
        elif cenario == 2:
            eu.update(box=True, pit_estado=4, vel=22.0)
            limitador = {"ativo": True, "vel": 79.0, "nos_boxes": True}
        lista = self._alertas.calcular({"bandeiras": bandeiras, "carros": carros, "comprimento": 5000.0,
                                        "limitador": limitador, "danos": None, "energia": None})
        return {"lista": lista, "limite_pit": self._alertas.limite_pit}
