# -*- coding: utf-8 -*-
"""Build av (P2.4) + aw (P2.3): TODO item de TODO painel, propriedade por propriedade: X, Y, fonte, negrito, italico, tamanho, cor,
visibilidade, persistencia e restauracao. Item sem efeito em alguma propriedade aplicavel = FALHA (sem 'qualquer uma serve').
Build aw:
  - cada propriedade e verificada em CADA cenario de dados em que o item aparece (o item tem de aparecer em pelo menos um);
  - persistencia com o salvar_config/carregar_config REAIS (config.json de verdade, 'reiniciando' o carregamento);
  - aparencia padrao comparada com a referencia CONGELADA da build au (arquivos da au desenhando em outro processo);
  - tamanhos conferidos contra a dimensao esperada e contra a build au;
  - as 6 janelas exclusivas do LMU e a Classificacao do LMU (foto e classico) entram na suite quando o pacote e o do LMU;
  - relogios congelados (nada de piscar/animar entre duas fotos).
Tambem: dependencias entre itens (aninhamento) tem de estar declaradas em DEPENDE e o Coach funciona item a item."""
import os, sys, json, tempfile, copy
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import numpy as np
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
import _render_au as RA
import _ref_au as RF
RA.congelar_relogio()                                     # build aw: nenhum quadro depende do tempo real
app = QApplication([]); SALVAR_REAL = o.salvar_config; o.salvar_config = lambda c_: None
import platform; from PySide6 import QtCore, __version__ as _pv
print("AMBIENTE: Python", platform.python_version(), "| PySide6", _pv, "| Qt", QtCore.qVersion(), "| plataforma Qt:", app.platformName(), "(QT_QPA_PLATFORM=%s)" % os.environ.get("QT_QPA_PLATFORM"), "| captura raster por QImage", flush=True)
o.carregar_fontes_corrida()                               # build aw: fontes de corrida registradas ANTES de qualquer janela (mesma condicao no processo da build au)      # (a persistencia real usa SALVAR_REAL)
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1
    else: falhas.append(msg); print("FALHA", msg)
cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
BASE_DADOS = demo.ler()

def arr(im):
    im = im.convertToFormat(im.Format.Format_RGBA8888)
    return np.frombuffer(bytes(im.constBits()), np.uint8).reshape(im.height(), im.width(), 4).astype(np.int16)
LIM_PIX = [12]
def difere(a, b):
    return a.size() != b.size() or int((np.abs(arr(a) - arr(b)).sum(axis=2) > 24).sum()) > LIM_PIX[0]
def iguais(a, b):
    return a.size() == b.size() and int((np.abs(arr(a) - arr(b)).sum(axis=2) > 24).sum()) <= 12

# ---- painéis ----------------------------------------------------------------------------------------------
CLS = {}
for n in dir(o):
    k = getattr(o, n)
    if isinstance(k, type) and issubclass(k, o.JanelaBase) and not n.startswith("_") and getattr(k, "ELEMENTOS", None) and k.CHAVE_ATIVO:
        CLS[k.CHAVE] = k
import ov_v18_janelas as v18
for k in v18.construir(o).values():
    if getattr(k, "ELEMENTOS", None): CLS[k.CHAVE] = k
import ov_classif_foto as cf
CLS["classificacao"] = cf.construir(o)
ORIGEM = {}                                               # chave de teste -> (origem, nome) para o desenho com a build au (veja _render_au.classe_de)
for _n in dir(o):
    _k = getattr(o, _n)
    if isinstance(_k, type) and issubclass(_k, o.JanelaBase) and not _n.startswith("_") and CLS.get(getattr(_k, "CHAVE", None)) is _k:
        ORIGEM[_k.CHAVE] = ("o", _n)
for _k in v18.construir(o).values():
    if CLS.get(_k.CHAVE) is _k or _k.CHAVE in CLS:
        ORIGEM.setdefault(_k.CHAVE, ("v18", _k.CHAVE))
ORIGEM["classificacao"] = ("cf", "")
# ---- build aw: janelas exclusivas do LMU (so existem no pacote do LMU) ----------------------------------------------
LMU = False
try:
    import overlay_lmu as _m
    import ov_demo_lmu as _dl
    import ov_janelas_extra_lmu as _ex
    import ov_janela_lmu as _jl
    LMU = True
except ImportError:
    pass
CFG_FORCA = {}
if LMU:
    cfg.update(_m.CONFIG_LMU_PADRAO)
    for _k in _ex.JANELAS_EXTRA:
        CLS["lmu:" + _k.CHAVE] = _k; ORIGEM["lmu:" + _k.CHAVE] = ("lmu_extra", _k.__name__)
    CLS["lmu:classificacao_foto"] = _jl.classe_classificacao(dict(cfg, classificacao_layout="foto")); ORIGEM["lmu:classificacao_foto"] = ("lmu_classif", "")
    CLS["lmu:classificacao_classico"] = _jl.classe_classificacao(dict(cfg, classificacao_layout="classico")); ORIGEM["lmu:classificacao_classico"] = ("lmu_classif", "")
    CFG_FORCA = {"lmu:classificacao_foto": {"classificacao_layout": "foto"}, "lmu:classificacao_classico": {"classificacao_layout": "classico"}}
CHAVE_DE = {K: ch for ch, K in CLS.items()}
confere(len(CLS) >= 36, f"paineis com itens ({len(CLS)})")
if LMU:
    for ex in ("lmu:lmu_energia", "lmu:pneus", "lmu:danos", "lmu:lmu_alertas", "lmu:lmu_stints", "lmu:lmu_tendencia", "lmu:classificacao_foto", "lmu:classificacao_classico"):
        confere(ex in CLS and CLS[ex].ELEMENTOS, f"P2.1: janela do LMU '{ex}' declara itens")
    confere(any(e == "ncars" for e, _r in CLS["lmu:classificacao_foto"].ELEMENTOS) and any(e == "ncars" for e, _r in CLS["lmu:classificacao_classico"].ELEMENTOS),
            "P2.1: N CARS e item nos dois layouts da Classificacao do LMU")
for ex in ("mapa", "forca_g", "luz_abs", "luz_tc", "trafego", "minimapa", "contato", "pit"):
    confere(ex in CLS, f"P2.3: painel {ex} declara itens")

# ---- cenarios de dados (o demo nao mostra estados vazios / de aprendizado) ---------------------------------------
def com(**mud):
    d = dict(BASE_DADOS)
    d.update(mud)
    return d
def mapa_incompleto():
    m = dict(BASE_DADOS.get("mapa") or {}); m["completo"] = False; m["progresso"] = 0.4
    return m
def dados_lmu(t, **mud):
    """Dados do LMU de exemplo no instante t (s) do demo; relogio proprio e fixo: determinístico."""
    rel = [5000.0 + t]
    dx = _dl.DemoExtraLMU(lambda: rel[0])
    d = dict(BASE_DADOS); d.update(dx.ler()); d.update(mud); return d
def _lmu_cenarios():
    z = lambda *a: None
    pneus_ruins = None
    c = {}
    d0 = dados_lmu(3.0)
    pn = copy.deepcopy(d0["lmu_pneus"]); pn["rodas"][0].update(furado=True, composto=None, temp=None, pressao=None, vida=None, freio=None); pn["rodas"][3].update(solta=True, otima=None)
    dn = copy.deepcopy(d0["lmu_danos"]); dn.update(zonas=[2, 0, 0, 0, 0, 0, 0, 0], solta=True, superaquecendo=True, farois=True, furados=[True, False, False, False], impacto_desde=None, impacto_forca=None, impacto_lado=None)
    dn0 = copy.deepcopy(d0["lmu_danos"]); dn0.update(zonas=[0] * 8, solta=False, superaquecendo=False, motor_parado=True, farois=False, furados=[False] * 4, rodas_soltas=[False] * 4, impacto_lado=None)
    st = copy.deepcopy(d0["lmu_stints"]); 
    c["lmu:lmu_energia"] = [d0, dados_lmu(23.0), dados_lmu(0.0, lmu_energia=dict(d0["lmu_energia"], limitante="energia", mensagem="sem_fim", ve_informada=False)), dados_lmu(0.0, lmu_energia=None)]
    c["lmu:pneus"] = [d0, dados_lmu(0.0, lmu_pneus=pn), dados_lmu(0.0, lmu_pneus=None)]
    c["lmu:danos"] = [d0, dados_lmu(0.0, lmu_danos=dn), dados_lmu(0.0, lmu_danos=dn0), dados_lmu(0.0, lmu_danos=None)]
    c["lmu:lmu_alertas"] = [dados_lmu(0.0), dados_lmu(6.0), dados_lmu(11.0), dados_lmu(16.0), dados_lmu(0.0, lmu_alertas={"lista": [], "limite_pit": None}), dados_lmu(0.0, lmu_alertas=None)]
    c["lmu:lmu_stints"] = [d0, dados_lmu(0.0, lmu_stints={"stints": []})]
    tend = d0["lmu_tendencia"]
    c["lmu:lmu_tendencia"] = [d0, dados_lmu(0.0, lmu_tendencia=dict(tend, inclinacao=None, delta_ritmo=None, temp_variacao=None)), dados_lmu(0.0, lmu_tendencia=None)]
    classif_vazio = None
    c["lmu:classificacao_foto"] = [d0, dados_lmu(0.0, classificacao=None)]
    c["lmu:classificacao_classico"] = [d0, dados_lmu(0.0, classificacao=None)]
    return c
CENARIOS = {
    "forca_g": [BASE_DADOS, com(forca_g=None)],
    "mapa": [BASE_DADOS, com(mapa=mapa_incompleto()), com(mapa=dict(BASE_DADOS["mapa"], carros=[]))],      # sem carros: a linha de largada aparece livre
    "minimapa": [BASE_DADOS, com(mapa=mapa_incompleto())],
}
if LMU:
    CENARIOS.update(_lmu_cenarios())
# itens sem texto: fonte/negrito/italico/tamanho nao se aplicam (so posicao, cor e visibilidade)
SEM_TEXTO = {("forca_g", "ponto"), ("mapa", "largada"), ("luz_abs", "brilho"), ("luz_tc", "brilho"), ("delta_trace", "anterior"),
             ("delta_trace", "ideal"), ("delta_trace", "mapa"), ("delta_trace", "grafico"), ("delta_trace", "blocos"), ("radar", "faixa"),
             ("radar", "brilho"), ("radar", "meu_carro"), ("pneus", "zonas"), ("pneus", "vida"), ("vazao", "mapa"), ("vazao", "trilha"),
             ("vazao", "cursor"), ("minimapa", "meu_carro"), ("auxiliar", "faixa"), ("bandeiras", "bandeira"), ("bandeiras", "borda"),
             ("classificacao", "barra"), ("digiflag", "borda"), ("digiflag", "painel"), ("estrategia", "nivel"), ("estrategia", "pneu"),
             ("luz_tc", "icone"), ("principal", "rpm"), ("sessao", "barra"),
             # build aw (LMU): fundos e desenhos sem texto
             ("lmu:classificacao_foto", "barra"), ("lmu:danos", "carro"), ("lmu:lmu_alertas", "fundo"), ("lmu:lmu_stints", "destaque"),
             ("lmu:lmu_tendencia", "grafico"), ("lmu:pneus", "cartoes")}
# itens para os quais a COR nao tem o que recolorir (so linhas/degrades, que de proposito nao mudam)
SEM_COR = {("classificacao", "barra"), ("forca_g", "ponto"), ("luz_abs", "brilho"), ("luz_tc", "brilho"), ("radar", "brilho"), ("radar", "faixa"),
           ("delta_trace", "anterior"), ("delta_trace", "ideal"), ("delta_trace", "grafico"), ("delta_trace", "mapa"), ("mapa", "largada"),
           ("vazao", "mapa"), ("vazao", "trilha"), ("vazao", "cursor"), ("pneus", "zonas"),
           # bandeiras e pneu da estrategia sao desenhados com traco/figura: a cor carrega o significado (amarela, azul...) e nao e trocada
           ("bandeiras", "bandeira"), ("bandeiras", "borda"), ("digiflag", "borda"), ("estrategia", "pneu"),
           # build aw (LMU): fundo translucido da barra e superficie dos cartoes (vem do tema, nao de um preenchimento liso)
           ("lmu:classificacao_foto", "barra"), ("lmu:pneus", "cartoes")}
EXC_VISIB_TESTE = set()

def desenha(K, dados, **extra):
    c2 = dict(cfg); c2.update(extra)
    c2[K.CHAVE_ATIVO] = False
    j = K(c2); j.atualizar(dados); return j, j.grab().toImage()

FINOS = {("mapa", "largada"), ("classificacao", "barra"), ("lmu:classificacao_foto", "barra")}           # tracos finos/fundo translucido: poucos pixels mudam
def efeito(K, chave, eid, extras_prop):
    """True se QUALQUER cenario de dados mostra diferenca para a propriedade (lista de variantes de config)."""
    LIM_PIX[0] = 0 if (chave, eid) in FINOS else 12
    for dados in CENARIOS.get(chave, [BASE_DADOS]):
        j0, base = desenha(K, dados)
        ch = j0._chave_elementos()
        for var in extras_prop(ch):
            _j, im = desenha(K, dados, **var)
            if difere(base, im):
                return True
    return False

PROPS = {
    "X": lambda ch, eid: [{ch + "_pos": {eid: [40, 0]}}, {ch + "_pos": {eid: [-40, 0]}}],
    "Y": lambda ch, eid: [{ch + "_pos": {eid: [0, 25]}}],
    "fonte": lambda ch, eid: [{ch + "_estilo": {eid: {"fonte": "bungee"}}}, {ch + "_estilo": {eid: {"fonte": "orbitron"}}}],
    "negrito": lambda ch, eid: [{ch + "_estilo": {eid: {"negrito": b}}} for b in (True, False)],
    "italico": lambda ch, eid: [{ch + "_estilo": {eid: {"italico": b}}} for b in (True, False)],
    "tamanho": lambda ch, eid: [{ch + "_estilo": {eid: {"tam": t}}} for t in (160, 60)],
    "cor": lambda ch, eid: [{ch + "_estilo": {eid: {"cor": "#ff00ff"}}}],
    "visibilidade": lambda ch, eid: [{ch: {eid: False}}],
}
def aplicavel(prop, chave, eid):
    if prop in ("fonte", "negrito", "italico", "tamanho") and (chave, eid) in SEM_TEXTO: return False
    if prop == "cor" and (chave, eid) in SEM_COR: return False
    return True

sem = []
total = 0
def aparece(K, chave, eid, dados):
    """O item aparece neste cenario de dados? (esconder o item muda a imagem)"""
    LIM_PIX[0] = 0 if (chave, eid) in FINOS else 12
    j0, base = desenha(K, dados)
    _j, im = desenha(K, dados, **{j0._chave_elementos(): {eid: False}})
    return difere(base, im)
def efeito_em(K, chave, eid, dados, fn):
    LIM_PIX[0] = 0 if (chave, eid) in FINOS else 12
    j0, base = desenha(K, dados)
    ch = j0._chave_elementos()
    return any(difere(base, desenha(K, dados, **var)[1]) for var in fn(ch, eid))
ONDE = {}                                                  # (chave, item) -> cenarios de dados em que o item aparece
for chave, K in sorted(CLS.items()):
    ids = [e for e, _r in K.ELEMENTOS]
    dep = getattr(K, "DEPENDE", {})
    cenarios = CENARIOS.get(chave, [BASE_DADOS])
    for eid in ids:
        onde = [n for n, dados in enumerate(cenarios) if aparece(K, chave, eid, dados)]
        ONDE[(chave, eid)] = onde
        total += 1
        if not onde: sem.append(f"{chave}.{eid}:nunca_aparece")         # item que nenhum cenario de dados exibe nao pode ser testado: e falha
        for prop, fn in PROPS.items():
            if prop == "visibilidade" or not aplicavel(prop, chave, eid): continue
            for n in onde:                                             # build aw: a propriedade tem de agir em CADA cenario em que o item aparece
                total += 1
                if not efeito_em(K, chave, eid, cenarios[n], fn):
                    sem.append(f"{chave}.{eid}:{prop}@cenario{n}")
    confere(o._ELEM_PILHA == [], f"{chave}: pilha limpa")
print("propriedades verificadas:", total)
confere(not sem, f"nenhum item/propriedade sem efeito ({len(sem)}): {sem}")

# ---- persistencia REAL (build aw): salvar_config/carregar_config de verdade, config.json em disco, "reiniciando" o carregamento ------------------
carregar_real = _m.carregar_config_lmu if LMU else o.carregar_config
confere(SALVAR_REAL.__name__ == "salvar_config" and SALVAR_REAL is not o.salvar_config, "persistencia: usa o salvar_config ORIGINAL (nao o substituto vazio)")
FONTES_OK = o.carregar_fontes_corrida()
confere("bungee" in FONTES_OK and "orbitron" in FONTES_OK, "fontes de corrida carregadas para o teste de persistencia")
for chave, K in sorted(CLS.items()):
    dados0 = CENARIOS.get(chave, [BASE_DADOS])[0]
    j0, base = desenha(K, dados0)
    ch = j0._chave_elementos()
    ids = [e for e, _r in K.ELEMENTOS]
    pos = {e: [10 + 7 * n, -6 + 5 * n] for n, e in enumerate(ids)}
    est = {e: {"fonte": ("bungee" if n % 2 == 0 else "orbitron"), "tam": 110 + 10 * (n % 5), "cor": "#%02x%02x%02x" % (20 + 15 * n % 200, 160, 220 - 9 * n % 180),
               "negrito": n % 2 == 0, "italico": n % 3 == 0} for n, e in enumerate(ids)}
    off = {ids[0]: False} if len(ids) > 1 else {}
    extra = {ch + "_pos": pos, ch + "_estilo": est, ch: off}
    _j, mem = desenha(K, dados0, **extra)                    # desenho com a config em memoria
    # grava de verdade
    total_cfg = dict(cfg); total_cfg.update(extra)
    o.ARQ_CONFIG.unlink(missing_ok=True)
    SALVAR_REAL(total_cfg)
    confere(o.ARQ_CONFIG.exists(), f"{chave}: config.json gravado em disco")
    bruto = json.loads(o.ARQ_CONFIG.read_text(encoding="utf-8"))
    confere(bruto.get(ch + "_pos") == pos and bruto.get(ch + "_estilo") == est and bruto.get(ch) == off, f"{chave}: o arquivo traz X/Y, fonte, tamanho, estilo, cor e visibilidade de todos os itens")
    # "reinicia": carrega de novo a partir do arquivo
    novo = carregar_real()
    confere(novo.get(ch + "_pos") == pos and novo.get(ch + "_estilo") == est and novo.get(ch) == off, f"{chave}: carregar_config devolve tudo igual ao que foi gravado")
    jl = K(dict(novo, **{K.CHAVE_ATIVO: False, "travado": True}))
    ok_val = True
    for e in ids:
        if jl._pos_elemento(e) != (float(pos[e][0]), float(pos[e][1])): ok_val = False
        eg = jl._estilo_elemento(e)
        if eg != est[e]: ok_val = False; print("   estilo lido", chave, e, eg, "!=", est[e])
    confere(ok_val, f"{chave}: apos reiniciar, cada item le X/Y, fonte, tamanho, negrito, italico e cor gravados")
    confere(jl.visivel(ids[0]) == (not off) and all(jl.visivel(e) or e in off or e in getattr(K, "DEPENDE", {}) for e in ids[1:]), f"{chave}: visibilidade gravada vale apos reiniciar")
    jl.atualizar(dados0); depois = jl.grab().toImage()
    confere(iguais(mem, depois), f"{chave}: o desenho apos reiniciar e igual ao desenho com a config em memoria")
    confere(difere(base, depois), f"{chave}: a personalizacao gravada muda o desenho (nao e ignorada)")
    # restaurar padroes: grava vazio, recarrega e volta ao desenho original
    vazio = {ch + "_pos": {}, ch + "_estilo": {}, ch: {}}
    total_cfg.update(vazio); SALVAR_REAL(total_cfg)
    novo2 = carregar_real()
    jr = K(dict(novo2, **{K.CHAVE_ATIVO: False, "travado": True})); jr.atualizar(dados0)
    confere(iguais(base, jr.grab().toImage()), f"{chave}: restaurar padroes (gravado e recarregado) devolve o desenho original")

# ---- dependencias: todo aninhamento observado precisa estar declarado em DEPENDE --------------------------------
pares = {}
orig_abre = o.JanelaBase._abre
def espiao(self, p, eid):
    r = orig_abre(self, p, eid)
    if r:
        pil = o._ELEM_PILHA
        pares.setdefault(type(self).__name__, set()).add((eid, len(pil)))
        if len(pil) >= 2:
            pares.setdefault("aninhados:" + type(self).__name__, set()).add((self._ultimo_aberto if hasattr(self, "_ultimo_aberto") else None, eid))
        self._ultimo_aberto = eid
    return r
nest = {}
def espiao2(self, p, eid):
    ant = len(o._ELEM_PILHA)
    topo = getattr(self, "_pilha_ids", [])
    r = orig_abre(self, p, eid)
    if r:
        ids = getattr(self, "_pilha_ids", None)
        if ids is None: ids = self._pilha_ids = []
        if len(o._ELEM_PILHA) > 1 and ids:
            nest.setdefault(CHAVE_DE.get(type(self), self.CHAVE), set()).add((ids[-1], eid))
        ids.append(eid)
    return r
orig_fecha = o.JanelaBase._fecha
def fecha2(p):
    for k in list(vars(o).values()): pass
    orig_fecha(p)
o.JanelaBase._abre = espiao2
# o espiao precisa saber quando fecha: troca _fecha para tirar o ultimo id de TODAS as janelas vivas
vivas = []
def fecha_espiao(p):
    for j in vivas:
        ids = getattr(j, "_pilha_ids", None)
        if ids and any(o._dono_da_entrada(e) is p for e in o._ELEM_PILHA):
            ids.pop(); break
    orig_fecha(p)
o.JanelaBase._fecha = staticmethod(fecha_espiao)
for chave, K in sorted(CLS.items()):
    for dados in CENARIOS.get(chave, [BASE_DADOS]):
        c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False
        j = K(c2); vivas[:] = [j]; j.atualizar(dados); j.grab()
o.JanelaBase._abre = orig_abre; o.JanelaBase._fecha = staticmethod(orig_fecha)
for chave, ps in nest.items():
    dep = getattr(CLS[chave], "DEPENDE", {})
    for pai, filho in ps:
        confere(dep.get(filho) == pai, f"{chave}: '{filho}' e desenhado dentro de '{pai}' e esta declarado em DEPENDE ({dep})")
print("aninhamentos observados:", {k: sorted(v) for k, v in nest.items()})

# dependentes: com o pai desligado, o filho some e a Central desabilita o interruptor
for chave in ("vazao", "marcha_efic", "destino"):
    K = CLS[chave]
    for filho, pai in K.DEPENDE.items():
        j0, base = desenha(K, BASE_DADOS)
        ch = j0._chave_elementos()
        _j, so_pai = desenha(K, BASE_DADOS, **{ch: {pai: False}})
        _j, os_dois = desenha(K, BASE_DADOS, **{ch: {pai: False, filho: False}})
        confere(iguais(so_pai, os_dois), f"{chave}: com '{pai}' desligado, '{filho}' nao desenha mais nada (dependencia consistente)")

# ---- Coach: cada item sozinho / combinacoes (P1.2) ---------------------------------------------------------------
Kc = CLS["coach"]
chc = Kc(dict(cfg, **{Kc.CHAVE_ATIVO: False}))._chave_elementos()
grupo = ("proxima", "freada", "marcha", "apice")
def img_off(off, **extra):
    return desenha(Kc, BASE_DADOS, **dict({chc: {e: False for e in off}}, **extra))
_j, tudo = img_off(())
for lig in grupo:
    off = tuple(e for e in grupo if e != lig)
    _j, so = img_off(off)
    _j, nada = img_off(grupo)
    confere(difere(so, nada), f"Coach: '{lig}' ligado sozinho (os outros 3 desligados) desenha")
    for outro in off:
        _j, comb = img_off(tuple(e for e in grupo if e not in (lig, outro)))
        confere(difere(comb, so), f"Coach: '{lig}' + '{outro}' desenha mais que '{lig}' sozinho")
    # X/Y, cor e fonte independentes, com o pai 'proxima' desligado
    for nome, extra in (("X", {chc + "_pos": {lig: [30, 0]}}), ("Y", {chc + "_pos": {lig: [0, 20]}}), ("cor", {chc + "_estilo": {lig: {"cor": "#ff00ff"}}}),
                        ("fonte", {chc + "_estilo": {lig: {"fonte": "bungee"}}})):
        _j, m = img_off(off, **extra)
        confere(difere(so, m), f"Coach: '{lig}' sozinho responde a {nome}")
_j, p0 = img_off(())
_j, p1 = img_off(grupo)
confere(difere(p0, p1), "Coach: tudo ligado difere de tudo desligado")
_ja, _ia = img_off(())
confere((_ia.width(), _ia.height()) == (max(40, round(_ja.tamanho()[0] * _ja.escala_x)), max(30, round(_ja.tamanho()[1] * _ja.escala_y))),
        f"Coach: a imagem tem a dimensao esperada (tamanho() x escala): {_ia.width()}x{_ia.height()}")
# compactacao: a faixa de cima so some quando os 4 estao desligados; nunca ha corte
j_all, _ = img_off(()); j_none, _ = img_off(grupo); j_one, _ = img_off(("proxima", "freada", "apice"))
confere(j_none.height() == j_all.height() - 82, f"Coach: os 4 desligados encolhem a janela em 82 px ({j_all.height()} -> {j_none.height()})")
confere(j_one.height() == j_all.height(), "Coach: com so a marcha ligada a faixa continua (sem sobrepor o delta)")
# padrao: sem personalizacao o desenho e o padrao (a comparacao com a referencia CONGELADA da build au esta na secao final)
confere(iguais(tudo, desenha(Kc, BASE_DADOS)[1]), "Coach: sem personalizacao o desenho e o padrao")

# ---- Central: item que so existe dentro de outro fica desabilitado enquanto o de fora estiver desligado -------------------
import ov_central as cc
reais = {k: K(dict(cfg, **{K.CHAVE_ATIVO: False})) for k, K in CLS.items() if k in ("vazao", "marcha_efic", "destino")}
def criar_previa(j):
    c2 = dict(cfg); c2[j.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j)(c2)
cen = cc.Central(list(reais.values()), {}, cfg, {"salvar": lambda: None, "registrar_erro": lambda e: None}, demo.ler, criar_previa, "Teste", "1.8.0")
cen.show(); cen.fonte_demo = lambda: BASE_DADOS
for chave in ("vazao", "marcha_efic", "destino"):
    reais[chave].config = cfg
    cen.abrir_detalhe(chave); app.processEvents()
    sw = cen._interruptores_delta
    for filho, pai in CLS[chave].DEPENDE.items():
        confere(sw[filho].isEnabled() and sw[pai].isChecked(), f"Central/{chave}: '{filho}' habilitado com '{pai}' ligado")
        sw[pai].definir(False); sw[pai].toggled.emit(False); app.processEvents()
        confere(not sw[filho].isEnabled(), f"Central/{chave}: '{filho}' desabilitado com '{pai}' desligado")
        sw[pai].definir(True); sw[pai].toggled.emit(True); app.processEvents()
        confere(sw[filho].isEnabled(), f"Central/{chave}: '{filho}' volta a habilitar")
# ---- build aw: aparencia padrao igual a da build au (referencia CONGELADA, desenhada em outro processo) ----------------------------------------
ok_zip, msg_zip = RF.conferir_zip()
confere(ok_zip, f"referencia au: arquivos e hashes conferem ({msg_zip})")
casos = []
for chave, K in sorted(CLS.items()):
    for n, dados in enumerate(CENARIOS.get(chave, [BASE_DADOS])):
        c = dict(cfg); c.update(CFG_FORCA.get(chave, {}))
        casos.append({"id": f"{chave}#{n}", "origem": ORIGEM[chave][0], "nome": ORIGEM[chave][1], "cfg": c, "dados": dados})
au = RF.desenhar_com_au(casos)
confere(len(au) == len(casos), f"referencia au: {len(casos)} imagens (paineis x cenarios de dados) desenhadas com os arquivos da build au")
atu = RF.desenhar_com_atual(casos)                        # os arquivos atuais, em processo limpo (a mesma condicao da referencia au)
LIM_PIX[0] = 0
dif = []
for c in casos:
    atual, ref = atu[c["id"]], au[c["id"]]
    if atual.size() != ref.size():
        dif.append(f"{c['id']}: tamanho {atual.width()}x{atual.height()} != au {ref.width()}x{ref.height()}")
    elif difere(atual, ref):
        dd = np.abs(arr(atual) - arr(ref)).sum(axis=2)
        ys, xs = np.where(dd > 24)
        dif.append(f"{c['id']}: {len(xs)} pixels diferentes da build au (ex.: x={xs[:3].tolist()} y={ys[:3].tolist()} dif={int(dd.max())})")
confere(not dif, f"aparencia padrao igual a da build au em todos os paineis e cenarios ({len(dif)} diferencas): {dif[:12]}")
# dimensao esperada de cada painel (tamanho() x escala) e valores absolutos conhecidos
EXPECT_BASE = {"lmu:lmu_energia": (372, 300), "lmu:pneus": (378, 350), "lmu:danos": (300, 334), "lmu:lmu_alertas": (392, 262),
               "lmu:lmu_stints": (590, 270), "lmu:lmu_tendencia": (540, 296)}
for chave, K in sorted(CLS.items()):
    for n, dados in enumerate(CENARIOS.get(chave, [BASE_DADOS])):
        j, im = desenha(K, dados)
        esp = (max(40, round(j.tamanho()[0] * j.escala_x)), max(30, round(j.tamanho()[1] * j.escala_y)))
        if (im.width(), im.height()) != esp:
            confere(False, f"{chave}#{n}: imagem {im.width()}x{im.height()} != dimensao esperada {esp}")
        if chave in EXPECT_BASE and (im.width(), im.height()) != EXPECT_BASE[chave]:
            confere(False, f"{chave}#{n}: dimensao {im.width()}x{im.height()} != {EXPECT_BASE[chave]} da build au")
confere(True, "dimensoes de todos os paineis conferidas contra tamanho() x escala e contra a build au")
if LMU:
    for ch_c in ("lmu:classificacao_foto", "lmu:classificacao_classico"):
        j, im = desenha(CLS[ch_c], CENARIOS[ch_c][0])
        confere(im.width() == 846, f"{ch_c}: largura 846 como na build au ({im.width()})")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
