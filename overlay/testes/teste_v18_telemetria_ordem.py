# -*- coding: utf-8 -*-
"""Build as: ordem dos itens da Telemetria (barra e painel). Validacao da ordem, ordem padrao identica a de sempre,
largura da janela estavel, desenho com qualquer ordem, Central (setas, Ordem original, previa ao vivo) e isolamento por layout."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import itertools
import overlay_iracing as o
import ov_central as c
from PySide6.QtWidgets import QApplication, QPushButton
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

K = o.JanelaTelemetria
PB = ("volante", "marcha", "velocidade", "pedais", "grafico"); PP = ("marcha", "velocidade", "pedais", "volante")
confere(K.ordem_blocos({}, True) == PB and K.ordem_blocos({}, False) == PP, "sem config: ordem original (barra e painel)")
confere(K.ordem_blocos({"telemetria_ordem_barra": []}, True) == PB, "lista vazia = ordem original")
confere(K.ordem_blocos({"telemetria_ordem_barra": ["pedais", "volante"]}, True) == ("pedais", "volante", "marcha", "velocidade", "grafico"), "ordem parcial: o que falta entra no fim, na ordem original")
confere(K.ordem_blocos({"telemetria_ordem_barra": ["pedais", "pedais", "xx", 5, None, "volante"]}, True) == ("pedais", "volante", "marcha", "velocidade", "grafico"), "ids repetidos/invalidos sao ignorados")
confere(K.ordem_blocos({"telemetria_ordem_painel": "marcha"}, False) == PP and K.ordem_blocos({"telemetria_ordem_painel": 7}, False) == PP, "tipo errado cai na ordem original")
confere(K.ordem_blocos({"telemetria_ordem_barra": ["grafico"]}, False) == PP, "ordem da barra nao vale para o painel")
confere(K.ordem_blocos(None, True) == PB, "config None nao quebra")
confere(sum(K.LARG_BLOCO_BARRA.values()) + 6 == o.LARGURA_BARRA - 8 + 8 - 0 - 0 + 0 or sum(K.LARG_BLOCO_BARRA.values()) + 6 <= o.LARGURA_BARRA, "barra: blocos cabem na largura")
confere(sum(K.LARG_BLOCO_PAINEL.values()) == o.LARGURA - 28, "painel: blocos somam a largura util")

cfg = o.carregar_config(); cfg["travado"] = True; cfg["telemetria_ordem_barra"] = []; cfg["telemetria_ordem_painel"] = []
demo = o.Telemetria(demo=True); demo.modo_previa = True
DADOS = demo.ler()

def render(config, barra, **extra):
    c2 = dict(config); c2["telemetria_barra"] = barra; c2.update(extra)
    c2[K.CHAVE_ATIVO] = False
    j = K(c2); j.atualizar(DADOS); j.resize(*j.tamanho()) if hasattr(j, "tamanho") else None
    return j, j.grab().toImage()

import numpy as np
def arr(im):
    im = im.convertToFormat(im.Format.Format_RGBA8888)
    return np.frombuffer(bytes(im.constBits()), np.uint8).reshape(im.height(), im.width(), 4).astype(np.int16)
def difere(a, b, ruido=0):
    return a.size() != b.size() or int((np.abs(arr(a) - arr(b)).sum(axis=2) > 24).sum()) > ruido * 2 + 40

for barra, ordens in ((True, PB), (False, PP)):
    nome = "barra" if barra else "painel"
    j0, base = render(cfg, barra)
    tam0 = j0.tamanho()
    rev = tuple(reversed(ordens)); chave = K.CHAVE_ORDEM_BARRA if barra else K.CHAVE_ORDEM_PAINEL
    j1, im1 = render(cfg, barra, **{chave: list(rev)})
    confere(j1.tamanho() == tam0, f"{nome}: a largura/altura da janela nao muda com a ordem {tam0}")
    confere(difere(base, im1), f"{nome}: ordem invertida desenha diferente")
    # toda permutacao desenha sem erro e mantem o tamanho
    ok = True; n = 0
    for perm in itertools.permutations(ordens):
        try:
            jx, _im = render(cfg, barra, **{chave: list(perm)}); n += 1
            ok = ok and jx.tamanho() == tam0
        except Exception as e:
            ok = False; print("   erro", perm, e); break
    confere(ok and n == len(list(itertools.permutations(ordens))), f"{nome}: {n} permutacoes desenham sem erro")
    j2, im2 = render(cfg, barra, **{chave: list(ordens)})
    confere(not difere(base, im2), f"{nome}: ordem explicita igual a original = imagem identica")

# sem grafico na barra: ordem continua valendo e a janela encolhe como antes
jg, _ = render(cfg, True, mostrar_grafico=False, telemetria_ordem_barra=["pedais", "volante", "marcha", "velocidade", "grafico"])
confere(jg.tamanho() == (o.LARGURA_BARRA_SEM_GRAFICO, o.ALTURA_BARRA), "barra sem grafico: tamanho original")
# o exemplo do pedido: volante a direita, pedais entre a marcha e o volante
ex = ["marcha", "velocidade", "pedais", "volante", "grafico"]
confere(K.ordem_blocos({"telemetria_ordem_barra": ex}, True) == tuple(ex), "exemplo do pedido (volante a direita, pedais antes dele) valido")

# Central
erros = []
reais = {"principal": K(dict(cfg, **{K.CHAVE_ATIVO: False}))}
def criar_previa(j):
    c2 = dict(cfg); c2[j.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j)(c2)
cen = c.Central(list(reais.values()), {}, cfg, {"salvar": lambda: None, "registrar_erro": erros.append}, demo.ler, criar_previa, "Teste", "1.8.0")
cen.show(); cen.fonte_demo = lambda: DADOS
# build av: comparacao visual DETERMINISTICA. A previa e a janela usam relogios (piscar, historico do grafico); sem congelar o tempo e
# sem o temporizador da Central, o numero de quadros desenhados entre duas fotos dependia da carga da maquina (falha intermitente).
import time as _t
_t.monotonic = lambda: 5000.0; _t.time = lambda: 1.7e9
for _tm in ("_timer_previa", "_timer"):
    if hasattr(cen, _tm):
        try: getattr(cen, _tm).stop()
        except Exception: pass
reais["principal"].config = cfg                          # em producao a janela real divide o mesmo config da Central
cen.abrir_detalhe("principal"); app.processEvents()
confere(set(getattr(cen, "_listas_ordem", {})) == {True, False}, "Central: listas de ordem dos dois layouts")
def img_previa():
    cen._ciclo_previa(); app.processEvents(); return cen.det_previa._pix.toImage()
def botoes(barra):
    lay = cen._listas_ordem[barra]; out = []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        out.append([b for b in w.findChildren(QPushButton)])
    return out
def clicar(barra, linha, lado):                           # lado 0 = esquerda, 1 = direita
    b = botoes(barra)[linha][lado]; confere(b.isEnabled(), f"botao ativo ({'barra' if barra else 'painel'} linha {linha} lado {lado})"); b.click(); app.processEvents()
barra_em_uso = bool(cfg.get("telemetria_barra", False))
confere(len(botoes(True)) == 5 and len(botoes(False)) == 4, "Central: 5 linhas na barra, 4 no painel")
confere(not botoes(True)[0][0].isEnabled() and not botoes(True)[-1][1].isEnabled(), "primeira nao sobe e ultima nao desce")
a0 = img_previa(); a0b = img_previa()
RZ = int((np.abs(arr(a0) - arr(a0b)).sum(axis=2) > 24).sum())
clicar(barra_em_uso, 0, 1)                                 # move o 1o item para a direita
ordem = K.ordem_blocos(cfg, barra_em_uso)
base = PB if barra_em_uso else PP
confere(ordem[0] == base[1] and ordem[1] == base[0], f"Central: seta troca os dois primeiros {ordem}")
confere(difere(img_previa(), a0, RZ), "Central: a previa muda na hora")
confere(K.ordem_blocos(cfg, not barra_em_uso) == (PP if barra_em_uso else PB), "Central: o outro layout nao foi alterado")
confere(reais["principal"].config.get(K.CHAVE_ORDEM_BARRA if barra_em_uso else K.CHAVE_ORDEM_PAINEL) == list(ordem), "Central: janela real recebeu a nova ordem")
clicar(barra_em_uso, 1, 0)                                 # volta
confere(K.ordem_blocos(cfg, barra_em_uso) == base, "Central: seta contraria desfaz")
clicar(barra_em_uso, 0, 1); clicar(not barra_em_uso, 0, 1)
bt = [b for b in cen.findChildren(QPushButton) if b.text() == "Ordem original"]
confere(bool(bt), "Central: botao 'Ordem original' existe")
bt[-1].click(); app.processEvents()
confere(K.ordem_blocos(cfg, True) == PB and K.ordem_blocos(cfg, False) == PP, "Ordem original restaura os dois layouts")
confere(not difere(img_previa(), a0, RZ), f"Ordem original devolve a previa original (ruido {RZ})")
confere(not erros, f"nenhum erro registrado ({erros[:2]})")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
