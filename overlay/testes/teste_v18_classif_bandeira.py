# -*- coding: utf-8 -*-
"""Build am: bandeira quadriculada na Classificacao (fundo ao encerrar a sessao + marca ao lado de quem terminou). Sem o jogo."""
import os, sys, tempfile, copy
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
import ov_classif_foto as cf
S = tempfile.mkdtemp()
# ---- logica pura
def cl(): return {"classes": [{"linhas": [{"idx": 0}, {"idx": 1}, {"idx": 2}]}, {"linhas": [{"idx": 3}]}]}
c = cl(); enc, n = cf.marcar_encerramento(c, 4, 0, [1, 1, 1, 1]); confere(not enc and n == 0 and not c["sessao_encerrada"], "corrida em andamento: nada marcado")
c = cl(); enc, n = cf.marcar_encerramento(c, 5, 0, [1, 0, 1, 0]); confere(enc and n == 2 and [l["finalizou"] for k in c["classes"] for l in k["linhas"]] == [True, False, True, False], "estado 5: marca quem tem o bit de quadriculada")
c = cl(); enc, n = cf.marcar_encerramento(c, 6, None, None); confere(enc and n == 0 and c["sessao_encerrada"], "estado 6 sem flags por carro: fundo sim, ninguem marcado")
c = cl(); enc, n = cf.marcar_encerramento(c, 4, 1, [1, 1, 1, 1]); confere(enc and n == 4, "bit de quadriculada em SessionFlags tambem encerra")
c = cl(); enc, n = cf.marcar_encerramento(c, None, None, None); confere(not enc and n == 0, "sem dados: nao encerrada")
c = cl(); enc, n = cf.marcar_encerramento(c, "x", "y", [1]); confere(not enc, "valores invalidos nao quebram")
c = cl(); enc, n = cf.marcar_encerramento(c, 5, 0, [1, 0]); confere(enc and n == 1, "lista curta de flags: o que falta nao e marcado")
c = cl(); enc, n = cf.marcar_encerramento(c, 5, 0, [None, 3, "a", 1]); confere(n == 2, "flags nulos/invalidos ignorados")
# ---- janela
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
o.ARQ_CONFIG = o.Path(S) / "c.json"; o.ARQ_LOG = o.Path(S) / "l.txt"
cfg = o.carregar_config()
confere(cfg.get("classif_bandeira_fundo") is True and cfg.get("classif_bandeira_coluna") is True, "opcoes ligadas por padrao")
J = cf.construir(o)(cfg)
tel = o.Telemetria(demo=True)
def dados(previa, t=3.0):
    tel.modo_previa = previa
    d = tel._demo(); d = dict(d); d["conectado"] = True
    return d
d0 = dados(False, 3.0)
tel._t0 -= 0  # a demo usa o relogio; para forcar o ciclo, chamamos o metodo direto
cla = tel._demo_classificacao(3.0); confere(not cla["sessao_encerrada"] and not any(l["finalizou"] for k in cla["classes"] for l in k["linhas"]), "demo no inicio do ciclo: corrida em andamento")
cla = tel._demo_classificacao(35.0); confere(cla["sessao_encerrada"] and any(l["finalizou"] for k in cla["classes"] for l in k["linhas"]), "demo no fim do ciclo: sessao encerrada com carros que terminaram")
tel.modo_previa = True
cla = tel._demo_classificacao(1.0); confere(cla["sessao_encerrada"], "previa da Central mostra a bandeira")
# largura e desenho
def montar(enc, **opc):
    c = copy.deepcopy(cfg); c.update(opc)
    j = cf.construir(o)(c)
    tel.modo_previa = enc
    d = dict(tel._demo()); d["conectado"] = True
    if not enc: d["classificacao"] = tel._demo_classificacao(3.0)
    j.atualizar(d); return j
j_run = montar(False); j_enc = montar(True); j_sem_col = montar(True, classif_bandeira_coluna=False)
confere(j_run._largura == cf.LARGURA_FOTO and j_run._extra == 0, f"corrida: largura padrao inalterada ({j_run._largura})")
confere(j_enc._extra == cf.EXTRA_BANDEIRA and j_enc._largura == cf.LARGURA_FOTO + cf.EXTRA_BANDEIRA, f"sessao encerrada: coluna extra ({j_enc._largura})")
confere(j_sem_col._extra == 0 and j_sem_col._largura == cf.LARGURA_FOTO, "opcao da coluna desligada: largura padrao")
def img(j): j.resize(int(j._largura), int(j._altura_base)); return j.grab().toImage()
a, b = img(j_enc), img(montar(True, classif_bandeira_fundo=False)); 
confere(a != b, "fundo da bandeira muda a imagem quando ligado")
r1, r2 = img(j_run), img(montar(False, classif_bandeira_fundo=False)); confere(r1 == r2, "sem encerrar, a opcao do fundo nao muda nada")
# a coluna aparece: pixels brancos/pretos na faixa extra
def faixa(im, j):
    x0 = int(j._largura_cols) + 2; cont = 0
    for y in range(im.height()):
        for x in range(x0, min(im.width(), x0 + 28)):
            c = im.pixelColor(x, y)
            if c.red() > 235 and c.green() > 235 and c.blue() > 235: cont += 1
    return cont
confere(faixa(a, j_enc) > 40, f"quadriculado desenhado ao lado de quem terminou ({faixa(a, j_enc)} px claros)")
a.save(os.path.join(S, "classif_bandeira.png")); print("png", os.path.join(S, "classif_bandeira.png"))
# opcoes_mudaram: ligar/desligar a coluna ao vivo
j = montar(True); w0 = j._largura; j.config["classif_bandeira_coluna"] = False; j.opcoes_mudaram(); w1 = j._largura; j.config["classif_bandeira_coluna"] = True; j.opcoes_mudaram()
confere(w0 == cf.LARGURA_FOTO + cf.EXTRA_BANDEIRA and w1 == cf.LARGURA_FOTO and j._largura == w0, "ligar/desligar a coluna ajusta a largura na hora")
# colunas escondidas: a coluna da bandeira acompanha o fim das colunas
j = montar(True, classif_colunas={"gap": False, "int": False}); confere(j._largura == j._largura_cols + cf.EXTRA_BANDEIRA and j._largura_cols < cf.LARGURA_FOTO, "com colunas escondidas a bandeira acompanha")
# Central
import ov_central as oc
extras = [k for k, _r in oc.PAINEIS["classificacao"][3]]
confere("classif_bandeira_fundo" in extras and "classif_bandeira_coluna" in extras, "Central: duas opcoes novas na Classificacao")
# sem dado nenhum / desconectado nao quebra
j = cf.construir(o)(copy.deepcopy(cfg)); d = dict(tel._demo()); d["conectado"] = False; j.atualizar(d); j.grab()
d = dict(tel._demo()); d["conectado"] = True; d["classificacao"] = None; j.atualizar(d); j.grab()
confere(j._extra == 0, "sem classificacao: sem coluna extra e sem erro")
print("ok" if not falhas else "FALHAS", _ok); sys.exit(1 if falhas else 0)
