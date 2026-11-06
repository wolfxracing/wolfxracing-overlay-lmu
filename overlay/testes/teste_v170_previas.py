# -*- coding: utf-8 -*-
"""Build t: a previa de TODO painel precisa mostrar algo (nunca ficar em branco) e nunca levantar erro, em qualquer instante da
demonstracao. Antes: Luz do ABS (sempre), Luz do TC, Auxiliar de sessao e Retorno a pista apareciam vazios boa parte do tempo."""
import collections, os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
import overlay_lmu as ol
extra = ol.extra_lmu
import ov_classif_foto as foto
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

ol.ARQ_CONFIG_LMU = S / "cl.json"
cfg = ol.carregar_config_lmu(); cfg["travado"] = True
Foto = foto.construir(o)
classes = {}
for n in dir(o):
    k = getattr(o, n)
    if isinstance(k, type) and issubclass(k, o.JanelaBase) and k.__dict__.get("CHAVE") and k is not o.JanelaBase:
        classes.setdefault(k.CHAVE, k)
classes["principal"] = o.JanelaTelemetria
for k in (extra.JanelaEnergiaLMU, extra.JanelaAlertasLMU, extra.JanelaStintsLMU, extra.JanelaTendenciaLMU,
          ol.JanelaClimaLMU, extra.JanelaPneusLMU, extra.JanelaDanosLMU):
    classes[k.CHAVE] = k          # o LMU troca estes paineis pelos proprios
classes["classificacao"] = ol.classe_classificacao(cfg)
ws = {}
for ch, k in classes.items():
    c2 = dict(cfg)
    if k.CHAVE_ATIVO: c2[k.CHAVE_ATIVO] = False
    ws[ch] = k(c2)
demo = ol.TelemetriaLMU(demo=True); demo.modo_previa = True; demo._demo.modo_previa = True
vazias, erros = collections.Counter(), collections.defaultdict(list)
for seg in range(0, 900, 6):
    demo._demo._t0 = time.time() - seg
    d = demo.ler()
    for ch, w in ws.items():
        try:
            w.atualizar(d); im = w.grab().toImage()
            if len({im.pixel(x, y) for x in range(0, im.width(), 5) for y in range(0, im.height(), 5)}) <= 2: vazias[ch] += 1
        except Exception as e:
            erros[ch].append(repr(e)[:80])
confere(len(ws) >= 30, f"{len(ws)} paineis verificados")
confere(not erros, f"nenhum painel levanta erro ao desenhar a previa em 15 min de demonstracao ({dict((k, v[0]) for k, v in erros.items())})")
confere(not vazias, f"nenhuma previa em branco ({dict(vazias)})")

# Central: a previa do painel aberto atualiza sozinha (~8x/s) e a de um painel de evento (Luz do ABS) nao fica vazia
import ov_central as c
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
menu = QMenu(); acoes = {}
jan = [ws[k] for k in ("luz_abs", "auxiliar", "principal")]
for j_ in jan:
    if j_.CHAVE_ATIVO:
        a_ = QAction(j_.CHAVE_ATIVO, menu); a_.setCheckable(True); a_.setChecked(True); acoes[j_.CHAVE_ATIVO] = a_
def _previa(j_):
    c2 = dict(cfg); c2[j_.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j_)(c2)
erros_c = []
cen = c.Central(jan, acoes, cfg, {"salvar": lambda: None, "registrar_erro": erros_c.append}, demo.ler, _previa, "Teste", "1.7.0")
cen.show(); cen.abrir_detalhe("luz_abs"); cen._ciclo_previa(); app.processEvents()
pix = cen.det_previa._pix
confere(pix is not None and not pix.isNull(), "prévia do painel aberto desenhada pelo ciclo rapido")
im_c = pix.toImage() if pix is not None else None
confere(im_c is not None and len({im_c.pixel(x, y) for x in range(0, im_c.width(), 3) for y in range(0, im_c.height(), 3)}) > 2, "Luz do ABS: a previa mostra a luz acesa")
confere(cen._timer_previa is not None and not erros_c, "sem erro registrado na Central")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
