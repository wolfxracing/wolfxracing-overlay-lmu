# -*- coding: utf-8 -*-
"""Atalhos globais (Stream Deck) dos 8 paineis da 1.8: mapa sem colisao, alvos existentes, iRacing e LMU. Logica pura; sem o jogo."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ov_nucleo as nu
falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
NOVOS = {"janela_vazao": "mostrar_vazao", "janela_marcha": "mostrar_marcha_efic", "janela_destino": "mostrar_destino", "janela_digiflag": "mostrar_digiflag",
         "janela_ultrapassagem": "mostrar_ultrapassagem", "janela_calendario": "mostrar_calendario", "janela_hibrido": "mostrar_hibrido", "janela_sessao": "mostrar_sessao"}
confere(nu.validar_atalhos() == [], f"mapa do iRacing valido ({nu.validar_atalhos()})")
for id_, chave in NOVOS.items():
    a = nu.atalho_por_id(id_)
    confere(a is not None and a.tipo == "alternar" and a.alvo == chave, f"iRacing: {id_} alterna {chave}")
nomes = [nu.atalho_por_id(i).nome for i in NOVOS]
confere(nomes == [f"Ctrl+F{n}" for n in range(13, 21)], f"iRacing: Ctrl+F13..F20 na ordem ({nomes})")
# os alvos tem de ser as chaves de 'mostrar' das janelas novas, e existir no padrao do config
import overlay_iracing as o
cl = o.v18_janelas.construir(o)
chaves = {K.CHAVE_ATIVO for K in cl.values()}
confere(set(NOVOS.values()) <= chaves, f"alvos = chaves das janelas da 1.8 ({set(NOVOS.values()) - chaves})")
S = tempfile.mkdtemp(); o.ARQ_CONFIG = o.Path(S) / "c.json"; o.ARQ_LOG = o.Path(S) / "l.txt"
cfg = o.carregar_config()
confere(all(k in cfg and cfg[k] is False for k in NOVOS.values()), "alvos existem no config e comecam desligados")
confere(len({a.id for a in nu.ATALHOS}) == len(nu.ATALHOS) and len({(a.mods, a.fn) for a in nu.ATALHOS}) == len(nu.ATALHOS), "sem id nem combinacao repetidos")
# codigo dos atalhos antigos nao muda (os novos entram no fim)
antigos = [a.id for a in nu.ATALHOS[:31]]
confere(antigos[0] == "janela_telemetria" and "janela_curvas" == antigos[-1], "atalhos antigos mantem a posicao no mapa")
# o mapa do LMU nao colide com o do iRacing
try:
    import ov_atalhos_lmu as al
    confere(al.validar_atalhos_lmu() == [], f"mapa do LMU valido e sem colisao com o iRacing ({al.validar_atalhos_lmu()})")
    nl = [al.ATALHOS_LMU[-8 + k].nome for k in range(8)]
    confere(nl == [f"Shift+F{n}" for n in range(13, 21)], f"LMU: Shift+F13..F20 ({nl})")
    confere({a.alvo for a in al.ATALHOS_LMU[-8:]} == set(NOVOS.values()), "LMU: mesmos alvos dos paineis novos")
except ImportError:
    pass

# ---- o perfil do Stream Deck distribuido traz os 8 atalhos novos com as teclas certas
import zipfile, json
from pathlib import Path as _P
_aqui = _P(__file__).resolve()
for _pasta in (_aqui.parents[1] / "streamdeck", _aqui.parents[2] / "streamdeck"):
    _arqs = sorted(_pasta.glob("Overlay iRacing.streamDeckProfile")) + sorted(_pasta.glob("Overlay LMU.streamDeckProfile"))
    if _arqs: break
for _arq in _arqs:
    _lmu = "LMU" in _arq.name
    _z = zipfile.ZipFile(_arq)
    _teclas = set()
    for _nm in _z.namelist():
        if _nm.endswith("manifest.json") and "/Profiles/" in _nm:
            for _c in json.loads(_z.read(_nm)).get("Controllers", []):
                for _a in (_c.get("Actions") or {}).values():
                    if _a["UUID"].endswith("hotkey"):
                        _h = _a["Settings"]["Hotkeys"][0]
                        if _h["VKeyCode"] != -1: _teclas.add((bool(_h["KeyCtrl"]), bool(_h["KeyShift"]), bool(_h["KeyOption"]), _h["VKeyCode"]))
    _mapa = (al.ATALHOS_LMU if 'al' in globals() else []) if _lmu else nu.ATALHOS
    for _id in NOVOS:
        _at = next(a for a in _mapa if a.id == _id)
        confere((bool(_at.mods & nu.MOD_CONTROL), bool(_at.mods & nu.MOD_SHIFT), bool(_at.mods & nu.MOD_ALT), _at.vk) in _teclas, f"perfil {_arq.name}: botao de {_id} envia {_at.nome}")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
