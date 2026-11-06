# -*- coding: utf-8 -*-
"""Build v (auditoria independente da build u): estados de espera/sem dados e combinacoes de elementos x escalas.
Regras verificadas, para Curvas, Setores, Coach, Consumo, Tendencia, Voltas e Delta Trace:
 (1) NADA e cortado: o desenho feito numa janela maior nao tem tinta fora da janela real (mensagem de espera inclusive);
 (2) a mensagem de espera nao se sobrepoe ao titulo;
 (3) cada secao ligada fica no lugar certo (banda do desenho completo, deslocada pelo que foi desligado acima), sem ser cortada ou
     coberta por outra;  (4) config antiga/corrompida nunca quebra e equivale a "tudo ligado";  (5) alternar dados/sem dados
     nao muda o tamanho nem deixa resto.  CAPTURAS_DIR=<pasta> grava as imagens-evidencia."""
import itertools, os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import numpy as np
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
CAP = os.environ.get("CAPTURAS_DIR")
if CAP: os.makedirs(CAP, exist_ok=True)
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
rico = demo.ler(); rico["conectado"] = True
rico["mapa"] = {"pontos": o._tracado_demo(), "completo": True, "versao": 1}
rico["setores"] = {"n": 3, "linhas": [{"tempo": 31.2 + k, "delta": 0.1 * k - 0.1, "roxo": k == 1, "ao_vivo": k == 2} for k in range(3)],
                   "ultima": {"tempo": 92.4, "delta": 0.2, "roxo": False}, "melhor": 91.9, "otima": 91.5, "pista": "P", "carro": "C"}
rico["delta_ok"] = True; rico["ultima_volta"] = 92.4; rico["melhor_volta"] = 91.9
rico["coach"] = o.JanelaCoach._exemplo()
ESTADOS = {                                  # nome -> dados
    "dados": rico,
    "desconectado": dict(rico, conectado=False),
    "espera": dict(rico, coach=None, tendencia=None, curvas=None, consumo=None, delta_trace=None, setores=None),
    "gravando": dict(rico, coach={"estado": "gravando"}, tendencia=None, curvas={"estado": "gravando"}, consumo=None),
}
PAINEIS = (o.JanelaCurvas, o.JanelaSetores, o.JanelaCoach, o.JanelaConsumo, o.JanelaTendencia, o.JanelaVoltas, o.JanelaDeltaTrace)

def janela(cls, off=(), escala=1.0, estado="dados", extra=None):
    c2 = dict(cfg)
    c2[cls.CHAVE_ELEMENTOS or ("elementos_" + cls.CHAVE)] = {e: False for e in off}
    c2["escala_x_" + cls.CHAVE] = c2["escala_y_" + cls.CHAVE] = escala
    if extra: c2.update(extra)
    j = cls(c2)
    try: j.atualizar(ESTADOS[estado])
    except Exception as e: return j, e
    app.processEvents()
    return j, None

def _arr(im):
    w, h = im.width(), im.height()
    im = im.convertToFormat(QImage.Format_ARGB32)
    return np.frombuffer(im.constBits(), dtype=np.uint8).reshape(h, im.bytesPerLine() // 4, 4)[:, :w].astype(int)

def img(j): return j.grab().toImage()
def dilatar(m):
    """Tolera 1 px (o degradê do fundo muda com a altura da janela e altera o limiar da borda do texto)."""
    d = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            d |= np.roll(np.roll(m, dy, 0), dx, 1)
    return d
def conteudo(j):
    """Mascara do CONTEUDO desenhado (texto, graficos): o que difere do painel vazio (fundo/borda) de mesmo tamanho e escala."""
    class Vazio(type(j)):
        def paintEvent(self, _e):
            p = self._pintor(); self._fundo(p, True)
    v = Vazio(dict(j.config)); v.setFixedSize(j.size()); v.atualizar(ESTADOS["dados"]); app.processEvents()
    a, b = _arr(img(j)), _arr(img(v))
    return np.abs(a - b).sum(-1) > 24

def cortada(j):
    """Tinta fora da janela real = conteudo cortado. Amplia a janela (o painel continua do mesmo tamanho) e conta o que sobra."""
    w, h = j.width(), j.height()
    j.setFixedSize(w + 400, h + 400); app.processEvents()
    t = conteudo(j); j.setFixedSize(w, h); app.processEvents()
    return int(t[h:, :].sum() + t[:, w:].sum())

# ---- 1/2) estados vazios e combinacoes x escalas --------------------------------------------------------------------------
print("== (1,2) nada cortado, mensagem sem sobrepor titulo")
for cls in PAINEIS:
    ids = [e for e, _ in cls.ELEMENTOS]
    combos = {"tudo": (), "nenhum": tuple(ids), "so_titulo": tuple(e for e in ids if e != "titulo") if "titulo" in ids else tuple(ids),
              "so_ultimo": tuple(e for e in ids if e != ids[-1])}
    for e in ids: combos["so_" + e] = tuple(x for x in ids if x != e)
    for e in ids: combos["sem_" + e] = (e,)
    for estado in ESTADOS:
        for escala in (0.5, 1.0, 1.5, 2.0):
            ruins = []
            for nome, off in combos.items():
                j, erro = janela(cls, off, escala, estado)
                if erro: ruins.append(f"{nome}:erro {erro!r}"); continue
                if cortada(j) > 0: ruins.append(f"{nome}:cortada({cortada(j)})")
            confere(not ruins, f"{cls.__name__} | {estado} | {int(escala*100)}% | {len(combos)} combinacoes sem corte ({ruins[:4]})")
# mensagem de espera x titulo
for cls, estado in ((o.JanelaCoach, "espera"), (o.JanelaCoach, "gravando"), (o.JanelaTendencia, "espera")):
    ids = [e for e, _ in cls.ELEMENTOS]
    for off in ((), tuple(e for e in ids if e != "titulo"), tuple(e for e in ids if e not in ("titulo", ids[-1]))):
        ja, _ = janela(cls, off, 1.0, estado); jb, _ = janela(cls, tuple(set(off) | {"titulo"}), 1.0, estado)
        a = conteudo(ja)
        sem_tit = conteudo(jb)
        tit = a & ~sem_tit
        msg = sem_tit
        if tit.any() and msg.any():
            ys_t, ys_m = np.where(tit)[0], np.where(msg)[0]
            confere(ys_t.max() < ys_m.min(), f"{cls.__name__} | {estado} | titulo termina na linha {ys_t.max()} e a mensagem comeca na {ys_m.min()} (sem sobrepor)")
        confere(msg.sum() > 100, f"{cls.__name__} | {estado} | mensagem de espera visivel ({int(msg.sum())} px de tinta)")

# ---- 3) cada secao ligada no lugar certo -------------------------------------------------------------------------------
print("\n== (3) secoes ligadas ficam no lugar certo (banda do desenho completo, deslocada)")
for cls in (o.JanelaCurvas, o.JanelaCoach, o.JanelaConsumo, o.JanelaTendencia, o.JanelaSetores):
    j0, _ = janela(cls); secs = j0._secoes(); ids = [e for e, _ in cls.ELEMENTOS]
    # tinta de cada secao sozinha (tudo o mais desligado), levada para as coordenadas do desenho completo
    sozinha = {}
    fixas = [e for e, _y, _h in secs if e not in ids]              # secoes sempre ligadas (ex.: a nota do rodape do Setores)
    jn, _ = janela(cls, tuple(ids)); tn = conteudo(jn)
    for eid, _y, _h in secs:
        if eid not in ids: continue
        js, _ = janela(cls, tuple(e for e in ids if e != eid))
        m = conteudo(js); dy = int(js._desloc(eid))
        for f in fixas:                                              # tira da secao a tinta das secoes fixas
            sh = int(jn._desloc(f) - js._desloc(f)); resto = np.roll(tn, sh, 0)
            hh = min(m.shape[0], resto.shape[0]); m[:hh] &= ~dilatar(resto[:hh, :m.shape[1]])
        sozinha[eid] = (m, dy)
    n_ruins = 0; n_tot = 0; pior = 1.0
    for combo in itertools.product((True, False), repeat=len(ids)):
        off = tuple(e for e, lig in zip(ids, combo) if not lig)
        j, _ = janela(cls, off); im = dilatar(conteudo(j))
        for eid, (m, dy_s) in sozinha.items():
            if eid in off or m.sum() < 30: continue
            dy = int(j._desloc(eid)); mov = dy_s - dy                      # a secao sozinha esta dy_s acima do lugar "cheio"; aqui, dy
            ys, xs = np.where(m)
            ys2 = ys + mov
            ok_pos = (ys2 >= 0) & (ys2 < im.shape[0]) & (xs < im.shape[1])
            if (~ok_pos).any(): n_ruins += 1; print(f"   ! {cls.__name__} {eid} sai da janela off={off}"); continue
            fr = im[ys2[ok_pos], xs[ok_pos]].mean(); n_tot += 1; pior = min(pior, fr)
            if fr < 0.97:
                n_ruins += 1
                if n_ruins <= 3: print(f"   ! {cls.__name__} secao {eid} off={off} fr={fr:.1%}")
    confere(n_ruins == 0, f"{cls.__name__}: {n_tot} secoes x combinacoes com a tinta da secao no lugar certo e inteira (pior caso {pior:.1%})")

# ---- 4) configuracao antiga/corrompida ---------------------------------------------------------------------------------
print("\n== (4) config antiga ou corrompida")
for cls in PAINEIS:
    chave = cls.CHAVE_ELEMENTOS or ("elementos_" + cls.CHAVE)
    ref = img(janela(cls)[0])
    for rotulo, valor in (("ausente", "__ausente__"), ("None", None), ("lista", [1, 2]), ("texto", "x"), ("numero", 7), ("vazio", {}),
                          ("valores estranhos", {e: v for e, v in zip([x for x, _ in cls.ELEMENTOS], (None, 0, "nao", [], 1, "False", 0.0, {}))})):
        c2 = dict(cfg)
        if valor != "__ausente__": c2[chave] = valor
        c2["escala_x_" + cls.CHAVE] = c2["escala_y_" + cls.CHAVE] = 1.0
        try:
            j = cls(c2); j.atualizar(ESTADOS["dados"]); app.processEvents(); im = img(j); ok = (im == ref)
        except Exception as e:
            ok = False; print("   erro", repr(e))
        confere(ok, f"{cls.__name__}: config '{rotulo}' = tudo ligado, sem excecao")
    # escala corrompida
    for esc in (None, "abc", -3, 99):
        c2 = dict(cfg); c2["escala_x_" + cls.CHAVE] = esc; c2["escala_y_" + cls.CHAVE] = esc
        try: j = cls(c2); j.atualizar(ESTADOS["dados"]); ok = j.width() >= 40 and j.height() >= 30
        except Exception as e: ok = False; print("   erro", repr(e))
        confere(ok, f"{cls.__name__}: escala corrompida {esc!r} nao quebra")

# ---- 5) alternar dados / sem dados -------------------------------------------------------------------------------------
print("\n== (5) alternancia dados x sem dados")
for cls in PAINEIS:
    ids = [e for e, _ in cls.ELEMENTOS]
    for off in ((), tuple(ids), tuple(ids[:-1]), tuple(ids[1:])):
        j, _ = janela(cls, off); tam = (j.width(), j.height()); ok = True
        for estado in ("dados", "espera", "desconectado", "gravando", "dados", "espera", "dados"):
            try: j.atualizar(ESTADOS[estado]); app.processEvents(); img(j)
            except Exception as e: ok = False; print("   erro", repr(e))
            ok = ok and (j.width(), j.height()) == tam
        fresco, _ = janela(cls, off)
        confere(ok and img(j) == img(fresco), f"{cls.__name__}: alternar estados mantem tamanho {tam} e termina igual ao desenho novo (off={len(off)})")

# ---- evidencias ----------------------------------------------------------------------------------------------------------
if CAP:
    n = 0
    for cls in (o.JanelaCoach, o.JanelaTendencia):
        ids = [e for e, _ in cls.ELEMENTOS]
        combos = {"tudo": (), "so_titulo": tuple(e for e in ids if e != "titulo"), "so_ultimo": tuple(e for e in ids if e != ids[-1]), "nenhum": tuple(ids)}
        for estado in ("espera", "gravando", "dados"):
            for nome, off in combos.items():
                for escala in (0.5, 1.0, 2.0):
                    if cls is o.JanelaTendencia and estado == "gravando": continue
                    j, _ = janela(cls, off, escala, estado)
                    j.grab().save(os.path.join(CAP, f"{cls.CHAVE}__{estado}__{nome}__{int(escala*100)}.png")); n += 1
    for cls in PAINEIS:
        ids = [e for e, _ in cls.ELEMENTOS]
        for nome, off in (("tudo", ()), ("nenhum", tuple(ids))):
            j, _ = janela(cls, off, 1.0, "dados"); j.grab().save(os.path.join(CAP, f"geral__{cls.CHAVE}__{nome}.png")); n += 1
    print(f"capturas gravadas: {n} em {CAP}")
print(f"\nRESULTADO: {len(falhas)} FALHA(S)" if falhas else f"\n{_ok} ok, 0 falha(s)")
sys.exit(1 if falhas else 0)
