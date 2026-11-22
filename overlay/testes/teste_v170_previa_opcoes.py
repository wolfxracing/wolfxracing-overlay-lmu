# -*- coding: utf-8 -*-
"""Build w: a previa ao vivo da Central precisa mudar quando QUALQUER opcao do painel muda (interruptores de acao e elementos).
Defeito da build v: a previa trabalhava numa copia do config feita ao criar; interruptores como 'Layout em barra horizontal'
(Telemetria) ou 'Calculo de combustivel' (Voltas) mudavam so a janela real e a previa ficava parada."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
import ov_central as c
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
classes = {"principal": o.JanelaTelemetria, "relativo": o.JanelaRelativo, "clima": o.JanelaClima, "pneus": o.JanelaPneus}
for n in dir(o):
    k = getattr(o, n)
    if isinstance(k, type) and issubclass(k, o.JanelaBase) and k.__dict__.get("CHAVE") and k is not o.JanelaBase:
        classes.setdefault(k.CHAVE, k)
if o.classif_foto is not None:      # build am: o painel real da Classificacao e o "foto" (a classica so existe como reserva)
    classes["classificacao"] = o.classif_foto.construir(o)
if o.v18_janelas is not None:                           # v1.8: as 8 janelas novas tambem precisam de previa que acompanhe as opcoes
    for ch, K in o.v18_janelas.construir(o).items():
        classes.setdefault(K.CHAVE, K)
reais = {}
for ch, K in classes.items():
    c2 = dict(cfg)
    if K.CHAVE_ATIVO: c2[K.CHAVE_ATIVO] = False
    reais[ch] = K(c2)
erros = []
def criar_previa(j):
    c2 = dict(cfg)
    if j.CHAVE_ATIVO: c2[j.CHAVE_ATIVO] = False
    c2["travado"] = True
    return type(j)(c2)
cen = c.Central(list(reais.values()), {}, cfg, {"salvar": lambda: None, "registrar_erro": erros.append}, demo.ler, criar_previa, "Teste", "1.7.0")
cen.show()

import numpy as np
DADOS = demo.ler()
cen.fonte_demo = lambda: DADOS                          # dados congelados: so a opcao muda entre uma imagem e outra
def previa_img(chave):
    cen._ciclo_previa(); app.processEvents()
    return cen.det_previa._pix.toImage()
def _arr(im):
    im = im.convertToFormat(im.Format.Format_RGBA8888)
    return np.frombuffer(bytes(im.constBits()), np.uint8).reshape(im.height(), im.width(), 4).astype(np.int16)
def difere(a, b, ruido=0):
    """True se as imagens diferem alem do ruido de animacao (graficos que andam com o tempo)."""
    if a.size() != b.size():
        return True
    return int((np.abs(_arr(a) - _arr(b)).sum(axis=2) > 24).sum()) > ruido * 2 + 40
def ruido_de(chave):
    a = previa_img(chave); b = previa_img(chave)
    return int((np.abs(_arr(a) - _arr(b)).sum(axis=2) > 24).sum()) if a.size() == b.size() else 0
# acoes que so mudam COMPORTAMENTO (quando o painel aparece / pisca), sem efeito visual na previa de exemplo
SO_COMPORTAMENTO = {"estrategia_pulsar", "auxiliar_sempre", "pit_sempre", "radar_auto", "digiflag_piscar", "hibrido_alerta", "ultrap_auto",
                    "ultrap_distante", "ultrap_so_outras", "ultrap_so_mesma_volta"}

# 1) interruptores de acao (extras de cada painel): a previa muda ao ligar/desligar
sem_efeito = []
for ch, (titulo, _d, _cat, extras, _dica) in c.PAINEIS.items():
    if ch not in reais:
        continue
    cen.abrir_detalhe(ch)
    for chave_acao, rotulo in extras:
        if chave_acao not in cfg and cen._acao(chave_acao) is None:
            continue
        rz = ruido_de(ch)
        antes = previa_img(ch)
        atual = bool(cfg.get(chave_acao))
        cen._set_acao(chave_acao, not atual)
        depois = previa_img(ch)
        mudou = difere(depois, antes, rz)
        cen._set_acao(chave_acao, atual)
        if not mudou and chave_acao in SO_COMPORTAMENTO:
            print("--   ", f"{titulo}: '{rotulo}' so muda comportamento (sem efeito visual na previa)")
            continue
        confere(mudou, f"{titulo}: '{rotulo}' muda a previa")

ESTADO_DEPENDE = {("forca_g", "aviso"), ("mapa", "largada"), ("mapa", "aviso"), ("minimapa", "aviso")}   # build av
# 2) elementos liga/desliga de cada painel que os declara
for ch, j in reais.items():
    if not type(j).ELEMENTOS or ch not in c.PAINEIS:
        continue
    cen.abrir_detalhe(ch)
    rz = ruido_de(ch)
    base = previa_img(ch)
    for eid, rotulo in type(j).ELEMENTOS:
        cen._ao_elemento(ch, eid, False)
        im = previa_img(ch)
        if not difere(im, base, rz) and (ch, eid) in ESTADO_DEPENDE:
            print("--   ", f"{c.PAINEIS[ch][0]}: '{rotulo}' so aparece em outro estado dos dados (verificado em teste_v18_itens_todos_paineis)")
        else:
            confere(difere(im, base, rz), f"{c.PAINEIS[ch][0]}: elemento '{rotulo}' muda a previa")
        cen._ao_elemento(ch, eid, True)
    confere(not difere(previa_img(ch), base, rz), f"{c.PAINEIS[ch][0]}: religar tudo devolve a previa original")

# 3) opacidade do fundo por painel muda a previa
cen.abrir_detalhe("principal")
rz = ruido_de("principal")
b0 = previa_img("principal")
cen.det_op.setValue(30); b1 = previa_img("principal")
confere(difere(b1, b0, rz), "Telemetria: opacidade propria do painel muda a previa")
cen.det_op.setValue(0)

# 4) em regime estavel a sincronizacao nao reaplica layout a cada ciclo (nada de reconfigurar() a 8x por segundo)
cen.abrir_detalhe("principal")
p = cen._previa("principal"); n = []
orig = p.aplicar_tamanho
p.aplicar_tamanho = lambda: (n.append(1), orig())[1]
for _ in range(10): cen._ciclo_previa()
confere(not n, f"sem mudanca de opcao a previa nao refaz o layout ({len(n)} chamadas)")
confere(not erros, f"nenhum erro registrado ({erros[:2]})")
# 5) layout: nenhuma linha de opcao passa da coluna de controles (build w: o Delta Trace tinha interruptores cortados)
from PySide6.QtWidgets import QScrollArea
cen.resize(1100, 760); app.processEvents()
for ch in c.PAINEIS:
    if ch not in reais:
        continue
    cen.abrir_detalhe(ch); app.processEvents()
    rol = [r for r in cen.findChildren(QScrollArea) if r.width() == 404 and r.widget() is not None]
    if not rol:
        continue
    w = rol[0].widget()
    largura_util = rol[0].viewport().width()
    confere(w.minimumSizeHint().width() <= largura_util, f"{c.PAINEIS[ch][0]}: opcoes cabem na coluna ({w.minimumSizeHint().width()} <= {largura_util})")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
