# -*- coding: utf-8 -*-
"""v1.8: as 9 janelas novas, a configuracao, a Central (paineis, temas, modo daltonico) e a correcao da persistencia dos elementos."""
import json, os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import numpy as np
import overlay_iracing as o
import ov_central as c
import ov_v18 as v18
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtGui import QImage, QColor

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

CHAVES = ("vazao", "marcha_efic", "destino", "digiflag", "ultrapassagem", "calendario", "hibrido", "sessao", "coach_pedais")
cfg = o.carregar_config(); cfg["travado"] = True
confere(o.ov_v18 is not None and o.v18_janelas is not None, "os modulos da v1.8 foram importados")
cl = o.v18_janelas.construir(o)
confere(tuple(cl) == CHAVES, f"construir devolve as 9 janelas ({tuple(cl)})")

# ---- configuracao: padroes, escalas por eixo, perfis
for k in CHAVES:
    confere(all(n in cfg for n in (f"x_{k}", f"y_{k}", f"mostrar_{k}", f"escala_{k}", f"escala_x_{k}", f"escala_y_{k}")), f"config: chaves de layout de '{k}'")
    confere(cfg[f"mostrar_{k}"] is False, f"config: '{k}' nasce desligada (nao polui a tela)")
confere(cfg["daltonismo"] == "padrao" and cfg["central_tema"] == "classico", "config: modo daltonico e tema da Central com padrao")
perf = o._PERFIS
confere(all(any(ch.startswith(p) for p in o.nucleo._PREFIXOS_LAYOUT) for ch in (f"x_{k}" for k in CHAVES)), "perfis: as chaves novas entram nos perfis de exibicao")

# ---- persistencia: config salva e recarregada (inclui o defeito corrigido dos 'elementos_*')
arq = S / "persist.json"
o.ARQ_CONFIG = arq
cfg2 = o.carregar_config()
cfg2["elementos_clima"] = {"neblina": False}
cfg2["elementos_vazao"] = {"legenda": False}
cfg2["mostrar_sessao"] = True; cfg2["daltonismo"] = "protanopia"; cfg2["sessao_hms"] = True; cfg2["ultrap_distante"] = True
arq.write_text(json.dumps(cfg2), encoding="utf-8")
cfg3 = o.carregar_config()
confere(cfg3["elementos_clima"] == {"neblina": False}, "persistencia: elementos do Clima sobrevivem ao reiniciar (correcao)")
confere(cfg3["elementos_vazao"] == {"legenda": False}, "persistencia: elementos de painel novo sobrevivem")
confere(cfg3["mostrar_sessao"] is True and cfg3["daltonismo"] == "protanopia" and cfg3["sessao_hms"] is True and cfg3["ultrap_distante"] is True, "persistencia: opcoes da v1.8")
for chave_el in ("elementos_relativo", "elementos_pneus", "elementos_voltas", "elementos_coach", "elementos_consumo", "elementos_curvas", "elementos_setores", "elementos_tendencia"):
    cfg2[chave_el] = {"x": False}
arq.write_text(json.dumps(cfg2), encoding="utf-8")
cfg3 = o.carregar_config()
confere(all(cfg3.get(k) == {"x": False} for k in ("elementos_relativo", "elementos_pneus", "elementos_voltas", "elementos_coach", "elementos_consumo", "elementos_curvas", "elementos_setores", "elementos_tendencia")), "persistencia: elementos de todos os paineis antigos")
arq.write_text(json.dumps({"elementos_clima": "texto-quebrado", "daltonismo": "padrao"}), encoding="utf-8")
confere(isinstance(o.carregar_config().get("elementos_clima", {}), dict), "persistencia: elementos corrompidos nao entram")
o.ARQ_CONFIG = S / "c.json"

# ---- janelas: pintam com dados variados sem erro, nunca cortam, encolhem com elementos desligados
demo = o.Telemetria(demo=True); demo.modo_previa = True
rico = demo.ler(); rico["conectado"] = True
vazio = o.Telemetria._vazio(); vazio["conectado"] = True
desc = dict(rico, conectado=False)
parciais = {"v18 None": dict(rico, v18=None), "v18 vazio": dict(rico, v18={}), "sessao None": dict(rico, v18=dict(rico["v18"], sessao=None, hibrido=None, calendario=[])),
            "vazio": vazio, "desconectado": desc}
def pinta(j, dados):
    j.atualizar(dados); j.show(); app.processEvents()
    return j.grab().toImage()
def _arr(im):
    im = im.convertToFormat(QImage.Format_ARGB32)
    return np.frombuffer(im.constBits(), dtype=np.uint8).reshape(im.height(), im.bytesPerLine() // 4, 4)[:, :im.width()].astype(int)
def tinta(im):
    return int((_arr(im)[:, :, 3] > 8).sum())
erros = []
o.registrar_erro = lambda ctx, *a, **k: erros.append(ctx)
for k, K in cl.items():
    c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False
    j = K(c2)
    base_im = pinta(j, rico)
    confere(tinta(base_im) > 500, f"{k}: desenha com os dados de exemplo ({tinta(base_im)} px)")
    for nome, d in parciais.items():
        try:
            im = pinta(j, d)
            confere(im.width() == j.width() and tinta(im) > 100, f"{k}: estado '{nome}' desenha algo ({tinta(im)} px) sem erro")
        except Exception as ex:
            confere(False, f"{k}: estado '{nome}' levantou {type(ex).__name__}: {ex}")
    confere(j.CHAVE_ATIVO == f"mostrar_{K.CHAVE}" and K.ELEMENTOS and K.ROTULO_MENU, f"{k}: tem chave ativa, elementos e rotulo de menu")
    # nada de tinta fora da janela: janela maior com tudo ligado == recorte
    h0 = j.height()
    c3 = dict(c2); c3[f"elementos_{K.CHAVE}"] = {e: False for e, _r in K.ELEMENTOS[1:]}
    j3 = K(c3); pinta(j3, rico)
    if K.SECOES:
        confere(j3.height() <= h0, f"{k}: com elementos desligados a janela encolhe ou fica igual ({j3.height()} <= {h0})")
    # escala por eixo
    c4 = dict(c2); c4[f"escala_x_{K.CHAVE}"] = 1.5; c4[f"escala_y_{K.CHAVE}"] = 0.8
    j4 = K(c4)
    confere(abs(j4.width() - round(K(c2).width() * 1.5)) <= 1 and abs(j4.height() - round(K(c2).height() * 0.8)) <= 1, f"{k}: escala por eixo respeitada")
confere(not erros, f"nenhum erro registrado durante o desenho ({erros[:3]})")

# ---- opcoes que mudam o desenho
def img(K, extra, dados=rico):
    c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False; c2.update(extra)
    j = K(c2); return pinta(j, dados)
def difere(a, b):
    return a.size() != b.size() or int((np.abs(_arr(a) - _arr(b)).sum(axis=2) > 24).sum()) > 60
Z = {k: v for k, v in rico.items()}
Z["v18"] = dict(rico["v18"])
confere(difere(img(cl["destino"], {"destino_litros": True}), img(cl["destino"], {"destino_litros": False})), "destino: opcao 'em litros' muda o desenho")
confere(difere(img(cl["vazao"], {"vazao_valores": True}), img(cl["vazao"], {"vazao_valores": False})), "vazao: opcao 'numeros nas celulas' muda o desenho")
confere(difere(img(cl["sessao"], {"sessao_hms": True}), img(cl["sessao"], {"sessao_hms": False})), "sessao: opcao h:mm:ss muda o desenho")
confere(difere(img(cl["calendario"], {"calendario_24h": False}), img(cl["calendario"], {"calendario_24h": True})), "calendario: opcao 24 h muda o desenho")
amarela = dict(rico, bandeira={"id": "amarela", "titulo": "AMARELA", "sub": "Cuidado", "cor": (250, 200, 40)})
confere(tinta(img(cl["digiflag"], {}, amarela)) > 500, "digiflag: bandeira amarela desenha")
quad = dict(rico, bandeira={"id": "quadriculada", "titulo": "FIM", "sub": "", "cor": (255, 255, 255)})
azul = dict(rico, bandeira={"id": "azul", "titulo": "AZUL", "sub": "Deixe passar", "cor": (60, 140, 255)})
confere(difere(img(cl["digiflag"], {}, quad), img(cl["digiflag"], {}, azul)), "digiflag: quadriculada e azul sao diferentes")
bat_baixa = dict(rico, v18=dict(rico["v18"], hibrido={"carga": 0.08, "deploy": 0.5, "ult_carga": None, "ult_deploy": None, "ativo": False}))
confere(tinta(img(cl["hibrido"], {}, bat_baixa)) > 500, "hibrido: bateria baixa desenha")
sem_hib = dict(rico, v18=dict(rico["v18"], hibrido=None))
confere(tinta(img(cl["hibrido"], {}, sem_hib)) > 200, "hibrido: carro sem sistema hibrido mostra o aviso")

# ---- ultrapassagem e a janela automatica: some sem alerta, aparece com alerta
K = cl["ultrapassagem"]
c2 = dict(cfg); c2["mostrar_ultrapassagem"] = True; c2["ultrap_auto"] = True; c2["travado"] = True
ju = K(c2)
ju.definir_auto_visivel(True)
ju.atualizar(dict(rico, v18=dict(rico["v18"], ultrapassagem={"carros": []}))); app.processEvents()
confere(not ju.isVisible(), "ultrapassagem: sem alerta a janela some")
ju.atualizar(rico); app.processEvents()
confere(ju.isVisible(), "ultrapassagem: com alerta a janela aparece")
c2["ultrap_auto"] = False
ju2 = K(c2); ju2.definir_auto_visivel(True)
ju2.atualizar(dict(rico, v18=dict(rico["v18"], ultrapassagem={"carros": []}))); app.processEvents()
confere(ju2.isVisible(), "ultrapassagem: opcao 'so com alerta' desligada deixa a janela sempre visivel")
c2["ultrap_auto"] = True; c2["travado"] = False
ju3 = K(c2); ju3.definir_auto_visivel(True)
ju3.atualizar(dict(rico, v18=dict(rico["v18"], ultrapassagem={"carros": []}))); app.processEvents()
confere(ju3.isVisible(), "ultrapassagem: destravada (modo mover) fica sempre visivel")

# ---- Central: paineis novos, previa, temas, modo daltonico
todas = []
for ch, Kc in cl.items():
    c2 = dict(cfg); c2[Kc.CHAVE_ATIVO] = False; todas.append(Kc(c2))
confere(all(ch in c.PAINEIS for ch in CHAVES), "Central: PAINEIS tem as 9 janelas novas")
gancho_dalt = []
errosc = []
def criar_previa(j):
    c2 = dict(cfg); c2[j.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j)(c2)
cfgc = dict(cfg)
cen = c.Central(todas, {}, cfgc, {"salvar": lambda: None, "registrar_erro": errosc.append, "daltonismo": gancho_dalt.append}, demo.ler, criar_previa, "Teste", "1.8.0")
cen.show(); app.processEvents()
for ch in CHAVES:
    cen.abrir_detalhe(ch); app.processEvents()
    confere(cen.det_previa._pix is not None, f"Central: detalhe de '{ch}' abre com previa")
cen.ir_para("aparencia"); app.processEvents()
rotulos = [b.text() for b in cen.p_aparencia.findChildren(QPushButton)]
confere(all(n in rotulos for n in ("Clássico escuro", "Vidro grafite", "Vidro gelo", "Vidro âmbar")), f"Central: seletor com os 3 temas de vidro + classico ({rotulos})")
confere(all(n in rotulos for n in ("Padrão", "Deuteranopia", "Protanopia", "Tritanopia")), "Central: seletor do modo daltonico")
imagens = {}
for tema in ("classico", "grafite", "gelo", "ambar"):
    cen._ao_tema_central(tema); app.processEvents()
    confere(cfgc["central_tema"] == tema and c.ACENTO == c.TEMAS_CENTRAL[tema]["acento"], f"Central: tema '{tema}' aplicado e gravado")
    confere(c.TEMAS_CENTRAL[tema]["acento"] in cen.styleSheet(), f"Central: folha de estilo do tema '{tema}'")
    imagens[tema] = cen.grab().toImage()
confere(all(difere(imagens[a], imagens[b]) for a in imagens for b in imagens if a < b), "Central: os 4 temas ficam visualmente diferentes")
cen._ao_tema_central("inexistente"); confere(c.ACENTO == c.TEMAS_CENTRAL["classico"]["acento"], "Central: tema desconhecido volta ao classico")
cen._ao_tema_central("classico")
cen._ao_daltonismo("deuteranopia")
confere(gancho_dalt == ["deuteranopia"] and cfgc["daltonismo"] == "deuteranopia", "Central: modo daltonico chama o gancho e grava")
cen.close()

# ---- modo daltonico de ponta a ponta: troca B.QColor, refaz COR_*, muda o desenho, e 'padrao' restaura TUDO
verde0, verm0 = (o.COR_VERDE.red(), o.COR_VERDE.green(), o.COR_VERDE.blue()), (o.COR_VERMELHO.red(), o.COR_VERMELHO.green(), o.COR_VERMELHO.blue())
cj = dict(cfg); cj["mostrar_pneus"] = False
jp = o.JanelaPneus(dict(cj)); jp.atualizar(rico)
ref = pinta(jp, rico)
ju_ = cl["ultrapassagem"](dict(cfg, mostrar_ultrapassagem=False))
ref_u = pinta(ju_, rico)
for modo in ("deuteranopia", "protanopia", "tritanopia"):
    v18.aplicar_daltonismo(o, modo)
    novo_verde = (o.COR_VERDE.red(), o.COR_VERDE.green(), o.COR_VERDE.blue())
    confere(isinstance(o.COR_VERDE, o._QColor_original) and isinstance(o.QColor(1, 2, 3), o._QColor_original), f"{modo}: o novo QColor continua sendo um QColor")
    if modo != "tritanopia":
        confere(novo_verde != verde0, f"{modo}: COR_VERDE mudou ({verde0} -> {novo_verde})")
        confere((o.COR_VERMELHO.red(), o.COR_VERMELHO.green(), o.COR_VERMELHO.blue()) != verm0, f"{modo}: COR_VERMELHO mudou")
    confere(o.QColor(128, 128, 128).red() == 128 and o.QColor(255, 255, 255).green() == 255, f"{modo}: cinza e branco nao mudam")
    confere(o.QColor(10, 20, 30, 77).alpha() == 77, f"{modo}: o alfa e preservado")
    confere(o.QColor("#336699").red() == 0x33, f"{modo}: QColor por texto continua funcionando")
    confere(o.QColor(o.QColor(200, 10, 10)).red() == o.QColor(200, 10, 10).red(), f"{modo}: copia de QColor nao e remapeada duas vezes")
    novo = pinta(jp, rico)
    confere(difere(novo, ref) or modo == "tritanopia", f"{modo}: a janela de Pneus desenha com outras cores")
    confere(not erros, f"{modo}: sem erro")
v18.aplicar_daltonismo(o, "deuteranopia"); v18.aplicar_daltonismo(o, "padrao")
confere((o.COR_VERDE.red(), o.COR_VERDE.green(), o.COR_VERDE.blue()) == verde0 and o.QColor is o._QColor_original, "padrao: restaura QColor e as constantes")
confere(not difere(pinta(jp, rico), ref) and not difere(pinta(ju_, rico), ref_u), "padrao: o desenho volta pixel a pixel ao original")
v18.aplicar_daltonismo(o, "inexistente")
confere(o.QColor is o._QColor_original, "modo desconhecido equivale a padrao")
# daltonismo e a Central/previa: a previa usa as mesmas cores
v18.aplicar_daltonismo(o, "deuteranopia")
a = pinta(o.JanelaPneus(dict(cj)), rico)
v18.aplicar_daltonismo(o, "padrao")
confere(difere(a, ref), "a previa (janela nova criada depois) ja nasce com as cores do modo")

# ---- LMU: extras da sessao e do hibrido a partir de uma estrutura do jogo
try:
    import overlay_lmu as lmu
    import types
    t = lmu.TelemetriaLMU(demo=True)
    info = types.SimpleNamespace(mMaxLaps=2147483647, mEndET=1800.0, mCurrentET=600.0, mSessionTimeRemaining=1200.0)
    tele = types.SimpleNamespace(mElectricBoostMotorState=2, mBatteryChargeFraction=0.64)
    ex = t._montar_extra_v18(info, None, tele, 3)
    confere(abs(ex["restante"] - 1200.0) < 1e-6 and ex["decorrido"] == 600.0 and ex["voltas_total"] is None and ex["voltas_rest"] is None, "LMU: sessao por tempo")
    confere(ex["hibrido"] == {"carga": 0.64, "deploy": None, "ativo": True}, "LMU: hibrido (propulsao)")
    tele.mElectricBoostMotorState = 0
    confere("hibrido" not in t._montar_extra_v18(info, None, tele, 3), "LMU: carro sem hibrido (estado 0) nao informa bateria")
    tele.mElectricBoostMotorState = 3; tele.mBatteryChargeFraction = float("nan")
    confere("hibrido" not in t._montar_extra_v18(info, None, tele, 3), "LMU: bateria invalida e ignorada")
    info2 = types.SimpleNamespace(mMaxLaps=20, mEndET=-1.0, mCurrentET=100.0, mSessionTimeRemaining=-1.0)
    ex2 = t._montar_extra_v18(info2, None, types.SimpleNamespace(mElectricBoostMotorState=1, mBatteryChargeFraction=0.5), 5)
    confere(ex2["voltas_total"] == 20 and ex2["voltas_rest"] == 15 and ex2["restante"] is None, "LMU: sessao por voltas")
    confere(t._extra_v18() == {} or isinstance(t._extra_v18(), dict), "LMU: _extra_v18 sem leitura previa devolve dicionario")
    d = t.ler()
    confere(isinstance(d.get("v18"), dict) and d["v18"]["vazao"]["maximo"], "LMU: a demonstracao traz os dados da v1.8")
except ImportError:
    print("--    (arvore do iRacing: sem overlay_lmu)")

# iRacing: _extra_v18 com variaveis falsas
class _IR:
    def __init__(self, v): self.v = v
    def __getitem__(self, k):
        if k not in self.v: raise KeyError(k)
        return self.v[k]
t = o.Telemetria(demo=True)
t.ir = _IR({"SessionTimeRemain": 900.0, "SessionTimeTotal": 1800.0, "SessionLapsRemainEx": 32767, "SessionLapsTotal": 32767,
            "EnergyERSBatteryPct": 0.42, "EnergyMGU_KLapDeployPct": 0.7, "PowerMGU_K": 120000.0})
ex = t._extra_v18()
confere(ex["restante"] == 900.0 and ex["decorrido"] == 900.0 and ex["voltas_rest"] is None and ex["voltas_total"] is None, "iRacing: sessao por tempo (32767 voltas = sem limite)")
confere(ex["hibrido"] == {"carga": 0.42, "deploy": 0.7, "ativo": True}, "iRacing: hibrido")
t.ir = _IR({"SessionTimeRemain": 86400.0 * 400, "SessionLapsRemainEx": 12, "SessionLapsTotal": 30})
ex = t._extra_v18()
confere(ex["restante"] is None and ex["voltas_rest"] == 12 and ex["voltas_total"] == 30 and "hibrido" not in ex, "iRacing: sessao por voltas, carro sem hibrido")
t.ir = _IR({"EnergyERSBatteryPct": 42.0})
confere(abs(t._extra_v18()["hibrido"]["carga"] - 0.42) < 1e-9, "iRacing: bateria em % (0..100) e normalizada")
t.ir = _IR({})
confere(t._extra_v18()["restante"] is None, "iRacing: sem variaveis nao quebra")

# =====================================================================================================================
# Build z - estados visuais da Eficiencia por marcha (media geral ponderada, 'RPM maximo observado')
# =====================================================================================================================
KM = cl["marcha_efic"]
PNG = os.environ.get("WOLFX_PNG_DIR")
def salva(im, nome):
    if PNG:
        os.makedirs(PNG, exist_ok=True); im.save(os.path.join(PNG, nome))
rotulos = dict(KM.ELEMENTOS)
confere(rotulos.get("troca") == "RPM máximo observado", "marcha: o rotulo da opcao agora e 'RPM maximo observado' (chave interna 'troca' mantida: configs antigas valem)")
confere(not any("troca" in r.lower() for e, r in KM.ELEMENTOS if e == "troca"), "marcha: nenhum rotulo sugere deteccao de troca")
ok_marcha = rico["v18"]["marcha"]
confere(all("rpm_max" in m and "rpm_troca" not in m for m in ok_marcha["marchas"]), "marcha: o dado de exemplo usa 'rpm_max'")
im_rpm = img(KM, {}, rico); im_sem = img(KM, {"elementos_marcha_efic": {"troca": False}}, rico); im_sem_par = img(KM, {"elementos_marcha_efic": {"troca": False, "parcela": False}}, rico)
confere(tinta(im_rpm) > 500 and difere(im_rpm, im_sem), "marcha (estado 1): com RPM maximo observado desenha as faixas de RPM")
confere(difere(im_sem, im_sem_par), "marcha (estado 2): sem RPM maximo observado, a parcela do tempo continua")
im_res = img(KM, {"elementos_marcha_efic": {"resumo": False}}, rico)
confere(difere(im_rpm, im_res) and im_res.height() < im_rpm.height(), "marcha (estado 3): sem o resumo (melhor/media/pior) a janela encolhe")
# sem dados de marcha / sem marcha atual / uma unica marcha / media ausente
d_vazio = dict(rico, v18=dict(rico["v18"], marcha={"marchas": [], "minimo": None, "maximo": None, "media": None, "atual": None}))
im_vz = img(KM, {}, d_vazio)
confere(tinta(im_vz) > 300 and difere(im_vz, im_rpm), "marcha (estado 4): sem dados de marcha -> grade vazia, sem erro")
uma = dict(ok_marcha, marchas=[ok_marcha["marchas"][2]], atual=3)
d_uma = dict(rico, v18=dict(rico["v18"], marcha=uma))
im_uma = img(KM, {}, d_uma)
confere(tinta(im_uma) > 300 and difere(im_uma, im_rpm), "marcha (estado 5): uma unica marcha com dados")
d_sem_media = dict(rico, v18=dict(rico["v18"], marcha=dict(ok_marcha, media=None)))
confere(difere(img(KM, {}, d_sem_media), im_rpm), "marcha (estado 6): media ausente muda o resumo (traco no lugar do valor)")
d_media = dict(rico, v18=dict(rico["v18"], marcha=dict(ok_marcha, media=ok_marcha["media"] + 25.0)))
confere(difere(img(KM, {}, d_media), im_rpm), "marcha (estado 7): a media geral exibida acompanha o dado")
d_atual = dict(rico, v18=dict(rico["v18"], marcha=dict(ok_marcha, atual=5)))
confere(difere(img(KM, {"marcha_destacar": True}, d_atual), img(KM, {"marcha_destacar": False}, d_atual)), "marcha (estado 8): destaque da marcha engatada")
d_desc = dict(rico, conectado=False)
im_dc = img(KM, {}, d_desc)
confere(tinta(im_dc) > 100 and difere(im_dc, im_rpm), "marcha (estado 9): jogo desconectado -> aviso")
d_none = dict(rico, v18=None); confere(tinta(img(KM, {}, d_none)) > 100, "marcha (estado 10): v18 ausente nao quebra")
for i_, (im_, nome_) in enumerate(((im_rpm, "padrao"), (im_sem, "sem_rpm_max"), (im_vz, "sem_dados"), (im_uma, "uma_marcha"), (im_dc, "desconectado"))):
    salva(im_, f"marcha_efic_{nome_}.png")
confere(not erros, f"marcha: nenhum erro registrado nos estados visuais ({erros[:3]})")

# =====================================================================================================================
# Build aa - redesenho visual do Mapa de vazao e da Eficiencia por marcha (referencias de estilo do piloto)
# =====================================================================================================================
KV = cl["vazao"]
vz = rico["v18"]["vazao"]
rotv = dict(KV.ELEMENTOS)
confere("trilha" in rotv and "resumo" in rotv and "cursor" in rotv, "vazao: elementos novos (resumo no topo, trilha) listados no painel")
confere(KV.LARG >= 420 and cl["marcha_efic"].LARG >= 420, "redesenho: janelas mais largas para eixos e numeros legiveis")
im_v = img(KV, {}, rico)
confere(tinta(im_v) > 500, "vazao (redesenho): desenha com dados de exemplo")
confere(difere(im_v, img(KV, {"elementos_vazao": {"trilha": False}}, rico)), "vazao: a trilha da posicao recente aparece e pode ser desligada")
confere(difere(im_v, img(KV, {"elementos_vazao": {"cursor": False}}, rico)), "vazao: o marcador da posicao atual pode ser desligado")
confere(difere(im_v, img(KV, {"elementos_vazao": {"resumo": False}}, rico)) and img(KV, {"elementos_vazao": {"resumo": False}}, rico).height() < im_v.height(), "vazao: resumo no topo pode ser desligado (janela encolhe)")
confere(difere(im_v, img(KV, {"vazao_valores": False}, rico)), "vazao: numeros nas celulas ligados por padrao e desligaveis")
confere(o.carregar_config()["vazao_valores"] is True, "vazao: padrao novo = mostra os numeros nas celulas")
sem_mapa = dict(rico, v18=dict(rico["v18"], vazao=dict(vz, mapa_motor=None)))
confere(difere(im_v, img(KV, {}, sem_mapa)), "vazao: o campo MAPA (motor) some quando o jogo nao informa")
sem_trilha = dict(rico, v18=dict(rico["v18"], vazao=dict(vz, trilha=[])))
confere(difere(im_v, img(KV, {}, sem_trilha)), "vazao: sem trilha nos dados nao desenha trilha")
ponta = dict(rico, v18=dict(rico["v18"], vazao=dict(vz, atual=(10, 9), trilha=[(0, 0), (5, 4), (10, 9)])))
confere(tinta(img(KV, {}, ponta)) > 500, "vazao: marcador no canto do mapa (100 %, ultima faixa) desenha sem erro")
sem_dados_v = dict(rico, v18=dict(rico["v18"], vazao=dict(celulas=[], maximo=None, minimo=None, atual=None, trilha=[], agora_lh=None, ultima_lv=None, medio_lv=None, rpm=None, rpm_max=None, mapa_motor=None, amostras=0)))
im_v0 = img(KV, {}, sem_dados_v)
confere(tinta(im_v0) > 300 and difere(im_v0, im_v), "vazao: sem dados -> mapa vazio com tracos, sem erro")
confere(tinta(img(KV, {}, dict(rico, conectado=False))) > 100, "vazao: jogo desconectado -> aviso")
KM2 = cl["marcha_efic"]
mz = rico["v18"]["marcha"]
im_m = img(KM2, {}, rico)
rotm = dict(KM2.ELEMENTOS)
confere("rpm_atual" in rotm and "legenda" in rotm and rotm["troca"] == "RPM máximo observado", "marcha (redesenho): elementos novos listados e rotulo 'RPM maximo observado' mantido")
confere(difere(im_m, img(KM2, {"elementos_marcha_efic": {"rpm_atual": False}}, rico)), "marcha: marcador do RPM atual aparece e pode ser desligado")
confere(difere(im_m, img(KM2, {"elementos_marcha_efic": {"troca": False}}, rico)), "marcha: linha/marcas do RPM maximo observado desligaveis")
im_nl = img(KM2, {"elementos_marcha_efic": {"legenda": False}}, rico)
confere(difere(im_m, im_nl) and im_nl.height() < im_m.height(), "marcha: legenda inferior desligavel (janela encolhe)")
confere(difere(img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=dict(mz, atual=2)))), img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=dict(mz, atual=5))))), "marcha: selo e destaque acompanham a marcha engatada")
confere(difere(im_m, img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=dict(mz, agora_l100=98.0))))), "marcha: consumo agora (L/100 km) no cabecalho acompanha o dado")
confere(difere(im_m, img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=dict(mz, rpm=None))))), "marcha: sem RPM atual o marcador some")
oito = dict(mz, marchas=[dict(m, marcha=k_) for k_, m in zip(range(1, 9), (mz["marchas"] * 2)[:8])], atual=8)
confere(tinta(img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=oito)))) > 500, "marcha: carro com 8 marchas desenha sem cortar")
confere(tinta(img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=dict(marchas=[], minimo=None, maximo=None, media=None, atual=None, agora_l100=None, rpm=None, rpm_max=None))))) > 300, "marcha: sem nenhum dado desenha sem erro")
for im_, nome_ in ((im_v, "vazao_padrao"), (img(KV, {"elementos_vazao": {"trilha": False}}, rico), "vazao_sem_trilha"), (im_v0, "vazao_sem_dados"), (img(KV, {}, ponta), "vazao_canto"),
                   (im_m, "marcha_padrao"), (img(KM2, {"elementos_marcha_efic": {"rpm_atual": False, "troca": False}}, rico), "marcha_sem_marcadores"),
                   (img(KM2, {}, dict(rico, v18=dict(rico["v18"], marcha=oito))), "marcha_8_marchas")):
    salva(im_, f"redesenho_{nome_}.png")
confere(not erros, f"redesenho: nenhum erro registrado ({erros[:3]})")

# =====================================================================================================================
# Build ac - Destino do combustivel (tabela por acelerador x RPM) e Central em galeria (lista lateral + cartoes)
# =====================================================================================================================
KD = cl["destino"]
im_d = img(KD, {}, rico)
rot_d = dict(KD.ELEMENTOS)
confere(KD.LARG >= 420 and tinta(im_d) > 500, "destino (redesenho): janela larga e desenha com os dados de exemplo")
confere(difere(im_d, img(KD, {"elementos_destino": {"rpm": False}}, rico)), "destino: cabecalho de RPM e cores por celula desligaveis")
confere(difere(im_d, img(KD, {"destino_litros": True}, rico)), "destino: celulas em litros mudam o desenho")
im_dt = img(KD, {"elementos_destino": {"totais": False}}, rico)
confere(difere(im_d, im_dt) and im_dt.height() < im_d.height(), "destino: barra a fundo/parcial/solto desligavel (janela encolhe)")
confere(difere(im_d, img(KD, {"elementos_destino": {"destaque": False}}, rico)), "destino: frase de maior zona desligavel")
dz = rico["v18"]["destino"]
confere(difere(im_d, img(KD, {}, dict(rico, v18=dict(rico["v18"], destino=dict(dz, atual=("FLAT", 9)))))), "destino: a celula atual (caixa branca) acompanha o dado")
confere(difere(im_d, img(KD, {}, dict(rico, v18=dict(rico["v18"], destino=dict(dz, stint_l=99.5, stint_voltas=34))))), "destino: stint no cabecalho acompanha o dado")
vz_d = dict(faixas=[], total_l=0.0, stint_l=0.0, stint_voltas=0, maior=None, atual=None, parcial=None, rpm_max=None)
confere(tinta(img(KD, {}, dict(rico, v18=dict(rico["v18"], destino=vz_d)))) > 300, "destino: sem dados desenha sem erro")
confere(tinta(img(KD, {}, dict(rico, conectado=False))) > 100, "destino: desconectado -> aviso")
salva(im_d, "redesenho_destino_padrao.png")
# ---- Central em galeria
cen.show(); cen.resize(1280, 780); cen.ir_para("paineis"); app.processEvents()
confere(len(cen._cartoes) == len(cen.janelas), "Central: um cartao por painel")
confere(all(c_["quadro"].objectName() == "cartao_g" for c_ in cen._cartoes.values()), "Central: cartoes em estilo de galeria")
confere({"Todos"} <= set(cen._cab_categoria) and len(cen._cab_categoria) >= 2, "Central: pilulas de categoria no topo")
cat_ex = next(k for k in cen._cab_categoria if k != "Todos")
cen._cab_categoria[cat_ex].click(); app.processEvents()
visiveis_c = [k for k, q in cen._cartoes.items() if not q["quadro"].isHidden()]
confere(visiveis_c and all(c.PAINEIS[k][2] == cat_ex for k in visiveis_c) and len(visiveis_c) < len(cen._cartoes), f"Central: clicar na categoria '{cat_ex}' filtra os cartoes")
confere(cen._cab_categoria[cat_ex].property("ativo") == "true" and cen._cab_categoria["Todos"].property("ativo") == "false", "Central: categoria ativa fica marcada")
cen._cab_categoria["Todos"].click(); app.processEvents()
confere(all(not q["quadro"].isHidden() for q in cen._cartoes.values()), "Central: 'Todos os paineis' mostra tudo")
cen.busca.setText("vazão"); app.processEvents()
confere("vazao" in [k for k, q in cen._cartoes.items() if not q["quadro"].isHidden()] and len([1 for q in cen._cartoes.values() if not q["quadro"].isHidden()]) < len(cen._cartoes), "Central: a busca continua filtrando a galeria")
cen.busca.setText(""); app.processEvents()
def colunas():
    return len({cen._grade.getItemPosition(i)[1] for i in range(cen._grade.count())})
cen.resize(1280, 780); app.processEvents(); cen._filtrar(); app.processEvents()
c_largo = colunas()
cen.resize(940, 700); app.processEvents(); cen._filtrar(); app.processEvents()
c_estreito = colunas()
confere(c_largo >= 2 and c_estreito <= c_largo and c_estreito >= 1, f"Central: colunas da galeria acompanham a largura ({c_largo} -> {c_estreito})")
cen.resize(1280, 780)
mini_g = cen._cartoes["destino"]["mini"]; mini_g.definir(None); app.processEvents()
confere(mini_g.grab().toImage().width() > 50, "Central: cartao sem previa nao quebra")
cen.ir_para("inicio"); app.processEvents()
confere(not errosc, f"Central (galeria): nenhum erro registrado ({errosc[:3]})")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
