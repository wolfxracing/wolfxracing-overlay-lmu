#!/usr/bin/env python3
"""Perfil Stream Deck XL 'Overlay LMU': mesmo formato do 'Overlay iRacing' (pagina principal + pasta Suporte).
Uso: python gerar_perfil_lmu.py <pasta_base_com_icones_e_layout> <pasta_do_pacote_lmu> <pasta_de_saida>
Os atalhos vem da tabela ATALHOS_LMU (ov_atalhos_lmu.py): nenhum comando e inventado aqui."""
import json, os, random, string, sys, uuid, zipfile
BIB, PACOTE, OUT_DIR = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, PACOTE)
import ov_nucleo as nu
import ov_atalhos_lmu as at

DEVICE_UUID, MODEL = "@(1)[4057/143/A00NA6053I6336]", "20GAT9902"       # Stream Deck XL (copiado do perfil exportado do usuario)
BASE = r"C:\WolfxRacing\wolfxracing-overlay-lmu\overlay"
LAY = json.load(open(f"{BIB}/layout_lmu.json"))
NOME = "Overlay LMU"

# icone -> (tipo, alvo)
ACAO = {
    "ctrl_economia_cpu": ("tecla", "economia_cpu"), "ctrl_aparecer_sozinho": ("tecla", "aparecer_sozinho"),
    "ctrl_travar_posicao": ("tecla", "travar_posicao"), "ctrl_zerar_pico_g": ("tecla", "zerar_pico_g"),
    "ctrl_classif_todas": ("tecla", "classif_todas"), "ctrl_manter_topo": ("tecla", "manter_no_topo"),
    "ctrl_restaurar_tamanhos": ("tecla", "restaurar_tamanhos"), "ctrl_fechar": ("tecla", "sair"),
    "ctrl_iniciar": ("abrir", "iniciar_overlay_lmu.bat"), "ctrl_forcar_fechamento": ("abrir", "fechar_overlay_lmu.bat"),
    "sup_demo": ("abrir", "testar_demo_lmu.bat"), "sup_log": ("abrir", "overlay_log_lmu.txt"), "sup_pasta_overlay": ("abrir", ""),
    "sup_pasta_suporte": ("pasta", ""), "sup_voltar": ("voltar", ""),
    "sup_atalhos": ("abrir", "ATALHOS_STREAM_DECK_LMU.txt"), "sup_guia": ("abrir", "LEIA-ME_LMU.txt"),
    "sup_roteiro": ("abrir", "ROTEIRO_VALIDACAO_LMU.txt"), "sup_testes": ("abrir", "executar_testes_lmu.bat"),
    "sup_diagnostico": ("abrir", "diagnostico_lmu.bat"), "sup_ver_diagnostico": ("abrir", "diagnostico_lmu.txt"),
}
for n in ("telemetria", "voltas", "classificacao", "clima", "combustivel", "forca_g", "energia", "pneus", "danos", "alertas", "stints", "tendencia"):
    ACAO[f"janela_{n}"] = ("tecla", f"janela_{n}")


def rid(): return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(26)) + "Z"
def estado(img): return {"FontFamily": "", "FontSize": 11, "FontStyle": "", "FontUnderline": False, "Image": img,
        "OutlineThickness": 2, "ShowTitle": False, "Title": "", "TitleAlignment": "bottom", "TitleColor": "#ffffff"}
VAZIO = {"KeyCmd": False, "KeyCtrl": False, "KeyModifiers": 0, "KeyOption": False, "KeyShift": False, "NativeCode": 146, "QTKeyCode": 33554431, "VKeyCode": -1}
def a_abrir(alvo, img):
    cam = BASE if not alvo else BASE + "\\" + alvo
    return {"ActionID": str(uuid.uuid4()), "LinkedTitle": True, "Name": "Open", "Plugin": {"Name": "Open", "UUID": "com.elgato.streamdeck.system.open", "Version": "1.0"},
            "Resources": None, "Settings": {"path": '"' + cam + '"'}, "State": 0, "States": [estado(img)], "UUID": "com.elgato.streamdeck.system.open"}
def a_tecla(atalho, img):
    sh, ct, al = bool(atalho.mods & nu.MOD_SHIFT), bool(atalho.mods & nu.MOD_CONTROL), bool(atalho.mods & nu.MOD_ALT)
    km = (1 if sh else 0) | (2 if ct else 0) | (4 if al else 0)
    t = {"KeyCmd": False, "KeyCtrl": ct, "KeyModifiers": km, "KeyOption": al, "KeyShift": sh, "NativeCode": atalho.vk, "QTKeyCode": 0x01000030 + (atalho.fn - 1), "VKeyCode": atalho.vk}
    return {"ActionID": str(uuid.uuid4()), "LinkedTitle": True, "Name": "Hotkey", "Plugin": {"Name": "Activate a Key Command", "UUID": "com.elgato.streamdeck.system.hotkey", "Version": "1.0"},
            "Resources": None, "Settings": {"Coalesce": True, "Hotkeys": [t, dict(VAZIO), dict(VAZIO), dict(VAZIO)]}, "State": 0, "States": [estado(img)], "UUID": "com.elgato.streamdeck.system.hotkey"}
def a_nada(img):
    """Botao decorativo: acao 'Hotkey' SEM nenhuma tecla configurada (nao envia nada). O Stream Deck exige uma acao para guardar a imagem."""
    return {"ActionID": str(uuid.uuid4()), "LinkedTitle": True, "Name": "Hotkey", "Plugin": {"Name": "Activate a Key Command", "UUID": "com.elgato.streamdeck.system.hotkey", "Version": "1.0"},
            "Resources": None, "Settings": {"Coalesce": True, "Hotkeys": [dict(VAZIO) for _ in range(4)]}, "State": 0, "States": [estado(img)], "UUID": "com.elgato.streamdeck.system.hotkey"}
def a_pasta(filha, img):
    return {"ActionID": str(uuid.uuid4()), "LinkedTitle": True, "Name": "Create Folder", "Plugin": {"Name": "Create Folder", "UUID": "com.elgato.streamdeck.profile.openchild", "Version": "1.0"},
            "Resources": None, "Settings": {"ProfileUUID": filha.lower()}, "State": 0, "States": [estado(img)], "UUID": "com.elgato.streamdeck.profile.openchild"}
def a_voltar(img):
    return {"ActionID": str(uuid.uuid4()), "LinkedTitle": True, "Name": "Parent Folder", "Plugin": {"Name": "Open Parent Folder", "UUID": "com.elgato.streamdeck.profile.backtoparent", "Version": "1.0"},
            "Resources": None, "Settings": {}, "State": 0, "States": [{"Image": img}], "UUID": "com.elgato.streamdeck.profile.backtoparent"}


def pagina(lay, raiz, pid, arq, filha=None):
    acoes = {}
    for pos, ic in lay.items():                      # pos = "coluna,linha"
        tipo, alvo = ACAO[ic]
        nome = rid() + ".png"
        arq[f"{raiz}/Profiles/{pid}/Images/{nome}"] = open(f"{BIB}/icones/png/{ic}.png", "rb").read()
        img = "Images/" + nome
        if tipo == "tecla":
            atalho = at.atalho_lmu_por_id(alvo); assert atalho is not None, alvo; a = a_tecla(atalho, img)
        elif tipo == "nada": a = a_nada(img)
        elif tipo == "abrir": a = a_abrir(alvo, img)
        elif tipo == "pasta": a = a_pasta(filha, img)
        else: a = a_voltar(img)
        acoes[pos] = a
    return {"Controllers": [{"Actions": acoes, "Type": "Keypad"}], "Icon": "", "Name": ""}


def main():
    assert at.validar_atalhos_lmu() == [], at.validar_atalhos_lmu()
    random.seed(20261031)
    prof, pg, padrao, filha = (str(uuid.uuid4()).upper() for _ in range(4))
    raiz = f"Profiles/{prof}.sdProfile"; arq = {}
    mp = pagina(LAY["principal"], raiz, pg, arq, filha)
    ms = pagina(LAY["suporte"], raiz, filha, arq)
    vazio = {"Controllers": [{"Actions": None, "Type": "Keypad"}], "Icon": "", "Name": ""}
    mprof = {"Device": {"Model": MODEL, "UUID": DEVICE_UUID}, "Name": NOME, "Pages": {"Current": pg.lower(), "Default": padrao.lower(), "Pages": [pg.lower()]}, "Version": "3.0"}
    pac = {"AppVersion": "7.4.2.22730", "DeviceModel": MODEL, "DeviceSettings": None, "FormatVersion": 1, "OSType": "Windows", "OSVersion": "10.0.26200",
           "RequiredPlugins": ["com.elgato.streamdeck.system.open", "com.elgato.streamdeck.system.hotkey", "com.elgato.streamdeck.profile.openchild", "com.elgato.streamdeck.profile.backtoparent"]}
    os.makedirs(OUT_DIR, exist_ok=True)
    saida = os.path.join(OUT_DIR, NOME + ".streamDeckProfile")
    dump = lambda o: json.dumps(o, separators=(",", ":"))
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("package.json", dump(pac)); z.writestr(f"{raiz}/manifest.json", dump(mprof))
        z.writestr(f"{raiz}/Profiles/{padrao}/manifest.json", dump(vazio))
        z.writestr(f"{raiz}/Profiles/{pg}/manifest.json", dump(mp)); z.writestr(f"{raiz}/Profiles/{filha}/manifest.json", dump(ms))
        for p, b in arq.items(): z.writestr(p, b)
    print(saida)


main()
