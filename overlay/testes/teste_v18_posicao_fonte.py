# -*- coding: utf-8 -*-
"""Build at: posicao livre (X/Y, arrastar na previa) e fonte de corrida por item, em todos os paineis com ELEMENTOS + Telemetria."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import numpy as np
import time as _tempo
_tempo.monotonic = lambda: 5000.0; _tempo.time = lambda: 1.7e9      # build ba: relogios congelados; a previa animada pelo relogio real oscilava entre capturas (falhava sob carga, ex.: runner do Windows)
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

# fontes embutidas
fd = o.fontes_corrida_disponiveis()
confere(len(fd) == len(o.FONTES_CORRIDA) == 9, f"9 fontes de corrida embutidas carregadas ({[r for _i, r in fd]})")
pasta = Path(o.__file__).parent / "fontes"
confere((pasta / "LICENCAS_OFL.txt").exists() and all((pasta / a).exists() for _i, _r, arqs, _n in o.FONTES_CORRIDA for a in arqs), "arquivos das fontes e licencas OFL presentes")
confere(o.carregar_fontes_corrida() is o.carregar_fontes_corrida(), "registro das fontes e feito uma vez")

cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
DADOS = demo.ler()
def arr(im):
    im = im.convertToFormat(im.Format.Format_RGBA8888)
    return np.frombuffer(bytes(im.constBits()), np.uint8).reshape(im.height(), im.width(), 4).astype(np.int16)
def difere(a, b, ruido=0):
    return a.size() != b.size() or int((np.abs(arr(a) - arr(b)).sum(axis=2) > 24).sum()) > ruido * 2 + 40
def janela(K, **extra):
    c2 = dict(cfg); c2.update(extra)
    if K.CHAVE_ATIVO: c2[K.CHAVE_ATIVO] = False
    j = K(c2); j.atualizar(DADOS); return j, j.grab().toImage()

K = o.JanelaTelemetria
chp = K(dict(cfg, **{K.CHAVE_ATIVO: False}))._chave_elementos()
confere(chp == "elementos_principal", "chave dos elementos da Telemetria")
j0 = K(dict(cfg, **{K.CHAVE_ATIVO: False}))
for ruim in (None, "x", {"marcha": "a"}, {"marcha": [1]}, {"marcha": [None, 2]}, {"marcha": 5}):
    j0.config[chp + "_pos"] = ruim
    confere(j0._pos_elemento("marcha") == (0.0, 0.0), f"posicao invalida {ruim!r} = (0, 0)")
j0.config[chp + "_pos"] = {"marcha": [9999, -9999]}
confere(j0._pos_elemento("marcha") == (j0.LIM_POS, -j0.LIM_POS), "posicao limitada a +-600 px")
j0.config[chp + "_estilo"] = {"marcha": {"fonte": "nao_existe", "cor": "vermelho", "negrito": "sim", "tam": "x"}, "velocidade": 5, "pedais": {"tam": 9999, "cor": "#12ab9F", "negrito": True, "italico": False, "fonte": "orbitron"}}
confere(j0._estilo_elemento("marcha") == {} and j0._estilo_elemento("velocidade") == {} and j0._estilo_elemento("volante") == {}, "estilo invalido, tipo errado ou ausente = padrao")
confere(j0._estilo_elemento("pedais") == {"fonte": "orbitron", "cor": "#12ab9F", "negrito": True, "italico": False, "tam": 200}, "estilo valido mantido e tamanho limitado a 200 %")

for barra in (True, False):
    nome = "barra" if barra else "painel"
    _j, base = janela(K, telemetria_barra=barra)
    _j, mov = janela(K, telemetria_barra=barra, **{chp + "_pos": {"marcha": [0, 20]}})
    confere(difere(base, mov), f"{nome}: mover a marcha 20 px para baixo muda o desenho")
    _j, zero = janela(K, telemetria_barra=barra, **{chp + "_pos": {"marcha": [0, 0]}})
    confere(not difere(base, zero), f"{nome}: posicao 0,0 = desenho original")
    _j, fon = janela(K, telemetria_barra=barra, **{chp + "_estilo": {"velocidade": {"fonte": "orbitron"}}})
    confere(difere(base, fon), f"{nome}: fonte Orbitron na velocidade muda o desenho")
    confere(o._ELEM_PILHA == [], f"{nome}: pilha de fontes limpa apos o desenho")
# o deslocamento nao muda o tamanho da janela
ja, _ = janela(K, telemetria_barra=True); jb, _ = janela(K, telemetria_barra=True, **{chp + "_pos": {"volante": [100, 5]}})
confere(ja.tamanho() == jb.tamanho(), "mover itens nao muda o tamanho da janela")
# a fonte de um item nao vaza para os outros
_j, so_marcha = janela(K, telemetria_barra=True, **{chp + "_estilo": {"marcha": {"fonte": "bungee"}}})
_j, so_vel = janela(K, telemetria_barra=True, **{chp + "_estilo": {"velocidade": {"fonte": "bungee"}}})
confere(difere(so_marcha, so_vel), "a fonte vale so para o item escolhido")
a_ = arr(so_marcha); b_ = arr(janela(K, telemetria_barra=True)[1])
confere(int((np.abs(a_[:, 150:] - b_[:, 150:]).sum(axis=2) > 24).sum()) < 60, "fonte da marcha nao mexe nos itens do lado direito")

# cor, negrito, italico e tamanho
_j, base_b = janela(K, telemetria_barra=True)
for rot, est in (("cor do texto", {"cor": "#ff0000"}), ("sem negrito", {"negrito": False}),
                 ("tamanho 150 %", {"tam": 150}), ("tamanho 60 %", {"tam": 60})):
    _j, im = janela(K, telemetria_barra=True, **{chp + "_estilo": {"velocidade": est}})
    confere(difere(base_b, im), f"estilo da velocidade: {rot} muda o desenho")
_it = [janela(K, telemetria_barra=True, **{chp + "_estilo": {"velocidade": {"italico": v}}})[1] for v in (True, False)]
confere(difere(base_b, _it[0]) or difere(base_b, _it[1]), "estilo da velocidade: italico/nao italico muda o desenho (o tema Sport ja e italico)")
_j, im_cor = janela(K, telemetria_barra=True, **{chp + "_estilo": {"marcha": {"cor": "#ff0000"}}})
A = arr(im_cor); B = arr(base_b)
reg = (slice(0, None), slice(64, 108))                      # onde fica a marcha na barra
vermelho = int(((A[reg][..., 0] > 200) & (A[reg][..., 1] < 60) & (A[reg][..., 2] < 60)).sum())
vermelho0 = int(((B[reg][..., 0] > 200) & (B[reg][..., 1] < 60) & (B[reg][..., 2] < 60)).sum())
confere(vermelho > vermelho0 + 100, f"a cor do texto aparece de fato na marcha ({vermelho0} -> {vermelho} px vermelhos)")
confere(int((np.abs(A[:, 150:] - B[:, 150:]).sum(axis=2) > 24).sum()) < 60, "a cor da marcha nao vaza para os outros itens")
pj, _ = janela(K, telemetria_barra=True)
import PySide6.QtGui as QG
pm = QG.QPixmap(10, 10); qp = QG.QPainter(pm); orig = qp.drawText
confere(pj._abre(qp, "marcha") is True, "abrir elemento")
pj.config[chp + "_estilo"] = {"marcha": {"cor": "#00ff00"}}
pj._fecha(qp)
pj._abre(qp, "marcha"); confere(qp.drawText != orig, "com cor propria o drawText e trocado so durante o item"); pj._fecha(qp)
confere("drawText" not in getattr(qp, "__dict__", {}), "ao fechar o item o drawText volta ao original")
qp.end()
confere(o._ELEM_PILHA == [], "pilha limpa")
# fonte do estilo: negrito/italico reais no QFont
o._ELEM_PILHA.append((None, {"negrito": True, "italico": True, "tam": 200}, None))
f = o.fonte(10)
confere(f.bold() and f.italic() and abs(f.pointSizeF() - 20.0) < 0.01, f"fonte(): negrito+italico+tamanho 200 % ({f.bold()}, {f.italic()}, {f.pointSizeF()})")
o._ELEM_PILHA[-1] = (None, {"negrito": False, "italico": False}, False)
f = o.fonte(10, o.QFont.Bold)
confere(not f.bold() and not f.italic(), "fonte(): estilo 'Normal' tira negrito e italico mesmo quando o painel pedia negrito")
o._ELEM_PILHA.clear()
f = o.fonte(10, o.QFont.Bold); confere(f.bold(), "fonte() sem estilo continua igual")

# todos os paineis com ELEMENTOS: mover/trocar fonte do 1o item nao quebra e deixa a pilha limpa
classes = {"principal": K}
for n in dir(o):
    k = getattr(o, n)
    if isinstance(k, type) and issubclass(k, o.JanelaBase) and k.__dict__.get("CHAVE") and k is not o.JanelaBase:
        classes.setdefault(k.CHAVE, k)
if o.v18_janelas is not None:
    for ch, Kx in o.v18_janelas.construir(o).items():
        classes.setdefault(Kx.CHAVE, Kx)
n_pan = 0; sem_efeito = []
for ch, Kx in sorted(classes.items()):
    if not Kx.ELEMENTOS:
        continue
    n_pan += 1
    k0 = Kx(dict(cfg, **{Kx.CHAVE_ATIVO: False})) if Kx.CHAVE_ATIVO else Kx(dict(cfg)); chv = k0._chave_elementos()
    _j, base = janela(Kx)
    mudou_algum = False; ok = True
    for eid, _r in Kx.ELEMENTOS:
        try:
            _j, im = janela(Kx, **{chv + "_pos": {eid: [30, 14]}, chv + "_estilo": {eid: {"fonte": "russo", "cor": "#ff2020", "tam": 120, "negrito": False, "italico": True}}})
            mudou_algum = mudou_algum or difere(base, im)
        except Exception as e:
            ok = False; print("   erro", ch, eid, e)
    confere(ok and o._ELEM_PILHA == [], f"{ch}: mover e trocar fonte de cada item sem erro")
    if not mudou_algum: sem_efeito.append(ch)
confere(n_pan >= 18, f"{n_pan} paineis com itens movimentaveis")
sem_efeito = [x for x in sem_efeito if x != "coach_pedais"]       # Pedais do Coach so desenha com o Coach ativo (sem dados na demo)
confere(not sem_efeito, f"em cada painel ao menos um item muda o desenho quando movido/trocado ({sem_efeito})")

# Central: campos X/Y, fonte, arrastar na previa, restaurar
erros = []
reais = {"principal": K(dict(cfg, **{K.CHAVE_ATIVO: False}))}
def criar_previa(j):
    c2 = dict(cfg); c2[j.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j)(c2)
salvos = []
cfg["telemetria_barra"] = True
cen = c.Central(list(reais.values()), {}, cfg, {"salvar": lambda: salvos.append(1), "registrar_erro": erros.append}, demo.ler, criar_previa, "Teste", "1.8.0")
cen.show(); cen.fonte_demo = lambda: DADOS; cen._dados_demo = DADOS
reais["principal"].config = cfg
cen.abrir_detalhe("principal"); cen._ciclo_previa(); app.processEvents()
confere(set(cen._campos_pos) >= {"volante", "marcha", "velocidade", "pedais"}, "Central: linha de X, Y e fonte para cada item")
def img(): cen._ciclo_previa(); app.processEvents(); return cen.det_previa._pix.toImage()
a0 = img(); _extra = [img() for _ in range(4)]          # build az: ruido = maior diferenca entre renderizacoes consecutivas (relogio real)
RZ = max(int((np.abs(arr(x) - arr(y)).sum(axis=2) > 24).sum()) for x, y in zip([a0] + _extra, _extra))
sx, sy, cb, ce, st, bc = cen._campos_pos["marcha"]
sy.setValue(12); app.processEvents()
confere(cfg.get(chp + "_pos", {}).get("marcha") == [0, 12], "Central: campo Y grava a posicao")
confere(difere(img(), a0, RZ), "Central: a previa muda na hora")
confere(reais["principal"].config.get(chp + "_pos") == {"marcha": [0, 12]}, "Central: janela real recebeu a posicao")
i = cb.findData("orbitron"); cb.setCurrentIndex(i); app.processEvents()
confere(cfg.get(chp + "_estilo") == {"marcha": {"fonte": "orbitron"}}, "Central: combo grava a fonte")
ce.setCurrentIndex(2); st.setValue(130); app.processEvents()
confere(cfg.get(chp + "_estilo") == {"marcha": {"fonte": "orbitron", "negrito": True, "italico": False, "tam": 130}}, f"Central: negrito/italico e tamanho gravados ({cfg.get(chp + '_estilo')})")
ce.setCurrentIndex(0); st.setValue(49); app.processEvents()
confere(cfg.get(chp + "_estilo") == {"marcha": {"fonte": "orbitron"}}, "Central: voltar a Padrao limpa negrito/italico/tamanho")
st.setValue(50); app.processEvents()                       # build av (P3): 50 % e um tamanho real, nao o padrao
confere(cfg.get(chp + "_estilo", {}).get("marcha", {}).get("tam") == 50 and st.minimum() == 49 and st.specialValueText() == "Tam. padrão", "Central: 50 % e selecionavel (Padrao e um valor a parte)")
st.setValue(49); app.processEvents()
confere("tam" not in cfg.get(chp + "_estilo", {}).get("marcha", {}), "Central: voltar a Padrao remove o tamanho")
from PySide6.QtWidgets import QColorDialog
from PySide6.QtGui import QColor as _QC
QColorDialog.getColor = staticmethod(lambda *a, **k: _QC("#ff8800"))
bc.click(); app.processEvents()
confere(cfg.get(chp + "_estilo", {}).get("marcha", {}).get("cor") == "#ff8800" and bc.text() == "#ff8800", "Central: botao de cor grava a cor")
cen._restaurar_pos_fonte("principal"); app.processEvents()
confere(not cfg.get(chp + "_pos") and not cfg.get(chp + "_estilo"), "Restaurar limpa posicoes e estilos")
confere(not difere(img(), a0, RZ), "Restaurar devolve a previa original")
# arrastar na previa: pressiona sobre a marcha (barra: x ~ 87, y ~ 36 em px base) e arrasta 20 px base para a direita e 10 para baixo
esc = cen._escala_previa("principal")
n_salvos = len(salvos)
cen._arrasto_ini(87 * esc, 36 * esc)
confere(getattr(cen, "_arr", None) is not None and cen._arr[1] == "marcha", f"arrastar: o item sob o mouse e a marcha ({getattr(cen, '_arr', None) and cen._arr[1]})")
cen._arrasto_mov(20 * esc, 10 * esc)
confere(cfg.get(chp + "_pos", {}).get("marcha") == [20, 10], f"arrastar: posicao acompanha o mouse ({cfg.get(chp + '_pos')})")
confere(cen._campos_pos["marcha"][0].value() == 20 and cen._campos_pos["marcha"][1].value() == 10, "arrastar: os campos X/Y acompanham")
confere(len(salvos) == n_salvos, "arrastar: nao grava o arquivo a cada movimento")
cen._arrasto_fim()
confere(len(salvos) == n_salvos + 1, "arrastar: grava ao soltar")
cen._arrasto_ini(-50, -50)
confere(getattr(cen, "_arr", None) is None, "clicar fora de qualquer item nao move nada")
cen._arrasto_ini(150 * esc, 36 * esc)                       # sobre a velocidade
confere(getattr(cen, "_arr", None) is not None and cen._arr[1] == "velocidade", "arrastar: velocidade identificada")
cen._arrasto_fim()
confere(not erros, f"nenhum erro registrado ({erros[:2]})")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
