# -*- coding: utf-8 -*-
"""Build u: elementos liga/desliga em Curvas, Setores, Coach, Consumo, Tendencia, Voltas (e Delta Trace pelo mesmo mecanismo).
Confere: tudo ligado = tamanho original; cada elemento desligado muda o painel (e encolhe a janela na altura exata da secao);
o que fica sobe sem deformar; 2^n combinacoes nao quebram (nem desequilibram o pintor); a Central mostra os interruptores e a
previa muda na hora."""
import itertools, os, random, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
import ov_central as c
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); salvos = []; o.salvar_config = lambda c_: salvos.append(1)
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
dados = demo.ler(); dados["conectado"] = True
dados["mapa"] = {"pontos": o._tracado_demo(), "completo": True, "versao": 1}
# painel com dados: Setores e Voltas com valores
dados["setores"] = {"n": 3, "linhas": [{"tempo": 31.2 + k, "delta": 0.1 * k - 0.1, "roxo": k == 1, "ao_vivo": k == 2} for k in range(3)],
                    "ultima": {"tempo": 92.4, "delta": 0.2, "roxo": False}, "melhor": 91.9, "otima": 91.5, "pista": "P", "carro": "C"}
dados["delta_ok"] = True; dados["ultima_volta"] = 92.4; dados["melhor_volta"] = 91.9

def janela(cls, off=(), extra=None):
    c2 = dict(cfg)
    chave = cls.CHAVE_ELEMENTOS or ("elementos_" + cls.CHAVE)
    c2[chave] = {e: False for e in off}
    if extra: c2.update(extra)
    j = cls(c2); j.atualizar(dados); app.processEvents()
    return j

def img(j): return j.grab().toImage()
def claros(im, lim=650):
    return {(x, y) for y in range(im.height()) for x in range(im.width()) if (lambda p: ((p >> 16) & 255) + ((p >> 8) & 255) + (p & 255) > lim)(im.pixel(x, y))}

PAINEIS = (o.JanelaCurvas, o.JanelaSetores, o.JanelaCoach, o.JanelaConsumo, o.JanelaTendencia, o.JanelaVoltas, o.JanelaDeltaTrace)
for cls in PAINEIS:
    nome = cls.__name__
    ids = [e for e, _ in cls.ELEMENTOS]
    print(f"\n== {nome}: {len(ids)} elementos")
    j0 = janela(cls)
    base = (j0.width(), j0.height()); im0 = img(j0)
    confere(len(ids) >= 3 and all(isinstance(r, str) and r for _, r in cls.ELEMENTOS), "declara elementos com rotulo")
    secoes = {e: h for e, _y, h in j0._secoes()}
    for eid in ids:
        jx = janela(cls, off=(eid,)); imx = img(jx)
        mudou = (jx.size() != j0.size()) or imx != im0
        confere(mudou, f"desligar '{eid}' muda o painel")
        if eid in secoes:
            confere(base[1] - jx.height() == secoes[eid], f"desligar '{eid}' encolhe exatamente {secoes[eid]} px ({base[1]}->{jx.height()})")
    # tudo desligado e todas as combinacoes sorteadas (ou todas, se forem poucas)
    jt = janela(cls, off=tuple(ids))
    confere(jt.width() >= 40 and jt.height() >= 30 and not img(jt).isNull(), "todos desligados: nao quebra, tamanho minimo mantido")
    combos = list(itertools.product((True, False), repeat=len(ids)))
    if len(combos) > 64: random.Random(7).shuffle(combos); combos = combos[:64]
    boas = True
    for combo in combos:
        jc = janela(cls, off=tuple(e for e, lig in zip(ids, combo) if not lig))
        if img(jc).isNull() or jc.height() < 30: boas = False
    confere(boas, f"{len(combos)} combinacoes desenham com tamanho valido")
    # tudo ligado de novo = original
    jr = janela(cls, off=())
    confere((jr.width(), jr.height()) == base and img(jr) == im0, "religar tudo devolve exatamente o desenho original")

print("\n== Compactacao: o que fica sobe sem deformar")
# Curvas sem o cartao: a lista e o rodape sobem 70 px (os pixels claros do texto coincidem)
j0 = janela(o.JanelaCurvas); jx = janela(o.JanelaCurvas, off=("cartao",))
a, b = claros(img(j0)), claros(img(jx))
alvo = {(x, y - 70) for x, y in a if y >= 100}
conf = len(alvo & b) / max(1, len(alvo))
confere(conf > 0.97, f"Curvas sem cartao: lista e rodape subiram 70 px sem deformar ({conf:.1%} dos pixels claros coincidem)")
# Consumo sem o bloco de numeros: faixa e trechos sobem 58 px
j0 = janela(o.JanelaConsumo); jx = janela(o.JanelaConsumo, off=("numeros",))
a, b = claros(img(j0)), claros(img(jx))
alvo = {(x, y - 58) for x, y in a if y >= 88}
conf = len(alvo & b) / max(1, len(alvo))
confere(conf > 0.95, f"Consumo sem numeros: faixa e trechos subiram 58 px ({conf:.1%})")
# Tendencia sem o grafico: a legenda sobe 116 px
j0 = janela(o.JanelaTendencia); jx = janela(o.JanelaTendencia, off=("grafico",))
a, b = claros(img(j0), 380), claros(img(jx), 380)          # a legenda e cinza
alvo = {(x, y - 130) for x, y in a if y >= 220}
conf = len(alvo & b) / max(1, len(alvo)) if len(alvo) > 30 else 0.0
confere(conf > 0.95, f"Tendencia sem grafico: legenda subiu 130 px ({conf:.1%})")
# Coach sem proxima: delta e ritmo sobem 82 px
j0 = janela(o.JanelaCoach); jx = janela(o.JanelaCoach, off=("proxima",))
a, b = claros(img(j0)), claros(img(jx))
alvo = {(x, y - 82) for x, y in a if y >= 106}
conf = len(alvo & b) / max(1, len(alvo))
confere(conf > 0.95, f"Coach sem proxima: o resto sobe 82 px ({conf:.1%})")

print("\n== Escala: a janela encolhida respeita o zoom")
j2 = janela(o.JanelaCurvas, off=("lista",), extra={"escala_curvas": 1.5, "escala_x_curvas": 1.5, "escala_y_curvas": 1.5})
confere(abs(j2.height() - round((252 - 126) * 1.5)) <= 1, f"Curvas a 150% sem a lista: altura {j2.height()}")

print("\n== Delta Trace continua com a chave propria (build r)")
jd = janela(o.JanelaDeltaTrace, off=("blocos",))
confere(o.JanelaDeltaTrace.CHAVE_ELEMENTOS == "delta_trace_elementos" and jd.height() < 200, "chave delta_trace_elementos e altura menor sem os blocos")

print("\n== Central: interruptores genericos e previa na hora")
menu = QMenu(); acoes = {}
jan = [janela(k) for k in (o.JanelaCurvas, o.JanelaConsumo, o.JanelaDeltaTrace, o.JanelaSetores, o.JanelaVoltas, o.JanelaCoach, o.JanelaTendencia)]
for j_ in jan:
    a_ = QAction(j_.CHAVE_ATIVO, menu); a_.setCheckable(True); a_.setChecked(True); acoes[j_.CHAVE_ATIVO] = a_
cfgc = dict(cfg)
for j_ in jan: j_.config = cfgc
def previa(j_):
    c2 = dict(cfgc); c2[j_.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j_)(c2)
erros = []
cen = c.Central(jan, acoes, cfgc, {"salvar": lambda: salvos.append(1), "registrar_erro": erros.append}, demo.ler, previa, "Teste", "1.7.0")
cen.show()
for chave, cls in (("curvas", o.JanelaCurvas), ("consumo", o.JanelaConsumo), ("setores", o.JanelaSetores), ("voltas", o.JanelaVoltas),
                   ("coach", o.JanelaCoach), ("tendencia", o.JanelaTendencia), ("delta_trace", o.JanelaDeltaTrace)):
    cen.abrir_detalhe(chave); app.processEvents()
    ints = getattr(cen, "_interruptores_delta", {})
    confere(set(ints) == {e for e, _ in cls.ELEMENTOS}, f"Central ({chave}): um interruptor por elemento")
real = cen._janela("curvas"); cen.abrir_detalhe("curvas"); app.processEvents()
h0 = real.height(); pix0 = cen.det_previa._pix.toImage() if cen.det_previa._pix is not None else None
cen._interruptores_delta["lista"].setChecked(False); app.processEvents()
confere(cfgc.get("elementos_curvas") == {"lista": False}, "desligar grava elementos_curvas no config")
confere(real.height() == h0 - 126, f"a janela real encolheu 126 px ({h0}->{real.height()})")
pix1 = cen.det_previa._pix.toImage() if cen.det_previa._pix is not None else None
confere(pix0 is not None and pix1 is not None and pix1 != pix0 and pix1.height() < pix0.height(), "a previa mudou na hora (e ficou mais baixa)")
cen._todos_elementos("curvas"); app.processEvents()
confere(cfgc.get("elementos_curvas") == {} and real.height() == h0 and all(i.isChecked() for i in cen._interruptores_delta.values()), "Mostrar todos restaura tudo")
confere(not erros, f"nenhum erro registrado pela Central ({erros})")
confere(salvos, "as mudancas pedem para salvar o config")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
for f in falhas: print(" -", f)
sys.exit(1 if falhas else 0)
