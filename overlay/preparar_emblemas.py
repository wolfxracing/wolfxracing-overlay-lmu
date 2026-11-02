# -*- coding: utf-8 -*-
"""
Prepara os emblemas das montadoras para o overlay.

Pega imagens soltas (PNG, JPG, WEBP ou SVG), corta as bordas vazias, centraliza num quadrado transparente
de 256 x 256 pixels e salva como PNG com o nome que o overlay procura (ex.: 'Logo_Aston Martin.svg' -> aston-martin.png).

Logos que vem com o nome escrito junto: coloque na mesma pasta de origem um arquivo "recortes.json" dizendo que parte
da imagem guardar (fracoes de 0 a 1: esquerda, topo, largura, altura), ex.: {"toyota": [0, 0, 0.28, 1], "alpine": [0, 0, 1, 0.58]}.
A chave especial "_clarear" lista marcas que devem virar brancas mesmo sem serem pretas (ex.: azul-marinho): {"_clarear": ["alpine"]}.

Uso (a partir da pasta do overlay):
    py -3.12 preparar_emblemas.py                 -> le a pasta 'emblemas\\novos' e grava em 'emblemas'
    py -3.12 preparar_emblemas.py C:\\Downloads   -> le outra pasta
    py -3.12 preparar_emblemas.py --tamanho 128   -> outro tamanho
    py -3.12 preparar_emblemas.py --nao-clarear   -> nao troca logos pretos por brancos

Logos pretos/cinza-escuros (monocromaticos) viram brancos por padrao, porque o overlay tem fundo escuro.
Os emblemas sao marcas registradas das montadoras: uso pessoal; nao publique em repositorio nem em release.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRect, QSize, Qt                      # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer                           # noqa: E402

EXTENSOES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
PASTA = Path(__file__).resolve().parent


def slug(texto):
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def nome_da_marca(arquivo):
    """'logo_aston martin (2).svg' -> 'aston-martin'. Tira prefixos/sufixos comuns de logo."""
    base = slug(Path(arquivo).stem)
    base = re.sub(r"^(logo|logos|emblema|emblem|badge|carlogo)-", "", base)
    base = re.sub(r"-(logo|logos|emblema|emblem|badge|carlogo|svg|png|vector|flat|simple|new|\d+)$", "", base)
    base = re.sub(r"-(logo|emblem|badge|\d+)$", "", base)
    return base or slug(Path(arquivo).stem)


def carregar(caminho, lado_maximo=1024):
    if caminho.suffix.lower() == ".svg":
        r = QSvgRenderer(str(caminho))
        if not r.isValid():
            return None
        tam = r.defaultSize()
        if tam.isEmpty():
            tam = QSize(512, 512)
        escala = lado_maximo / max(tam.width(), tam.height())
        img = QImage(max(1, int(tam.width() * escala)), max(1, int(tam.height() * escala)), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        r.render(p)
        p.end()
        return img
    img = QImage(str(caminho))
    return None if img.isNull() else img.convertToFormat(QImage.Format_ARGB32)


def caixa_visivel(img, limiar=8):
    """Retangulo que contem os pixels nao transparentes."""
    x0, y0, x1, y1 = img.width(), img.height(), -1, -1
    for y in range(img.height()):
        for x in range(img.width()):
            if (img.pixel(x, y) >> 24) & 0xFF > limiar:
                x0, x1 = min(x0, x), max(x1, x)
                y0, y1 = min(y0, y), max(y1, y)
    return None if x1 < 0 else QRect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def tirar_fundo_branco(img):
    """JPG/PNG sem transparencia: se os 4 cantos forem brancos, torna o branco transparente."""
    w, h = img.width(), img.height()
    cantos = [img.pixelColor(0, 0), img.pixelColor(w - 1, 0), img.pixelColor(0, h - 1), img.pixelColor(w - 1, h - 1)]
    if any(c.alpha() < 250 for c in cantos) or not all(c.red() > 240 and c.green() > 240 and c.blue() > 240 for c in cantos):
        return img
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            m = min(c.red(), c.green(), c.blue())
            if m > 235:
                c.setAlpha(0)
                img.setPixelColor(x, y, c)
            elif m > 200:
                c.setAlpha(int(255 * (235 - m) / 35))
                img.setPixelColor(x, y, c)
    return img


def e_escuro_monocromatico(img):
    """True se o desenho visivel for quase todo preto/cinza-escuro (some em fundo escuro)."""
    total = escuros = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if c.alpha() < 128:
                continue
            total += 1
            if max(c.red(), c.green(), c.blue()) < 90 and max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) < 40:
                escuros += 1
    return total > 0 and escuros / total > 0.85


def clarear(img):
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha():
                img.setPixelColor(x, y, QColor(255, 255, 255, c.alpha()))
    return img


def recortar(img, fracoes):
    """Guarda so uma parte da imagem: fracoes = (esquerda, topo, largura, altura), de 0 a 1."""
    e, t, l, a = fracoes
    x, y = int(round(e * img.width())), int(round(t * img.height()))
    w, h = max(1, int(round(l * img.width()))), max(1, int(round(a * img.height())))
    return img.copy(QRect(x, y, min(w, img.width() - x), min(h, img.height() - y)))


def preparar(img, lado, margem=0.06, claro=True, recorte=None, forcar_claro=False):
    if recorte:
        img = recortar(img, recorte)
    img = tirar_fundo_branco(img)
    caixa = caixa_visivel(img)
    if caixa is None:
        return None, False
    corte = img.copy(caixa)
    trocou = False
    if forcar_claro or (claro and e_escuro_monocromatico(corte)):
        corte = clarear(corte)
        trocou = True
    util = int(lado * (1 - 2 * margem))
    corte = corte.scaled(util, util, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    saida = QImage(lado, lado, QImage.Format_ARGB32)
    saida.fill(Qt.transparent)
    p = QPainter(saida)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage((lado - corte.width()) // 2, (lado - corte.height()) // 2, corte)
    p.end()
    return saida, trocou


def principal(argv=None):
    ap = argparse.ArgumentParser(description="Padroniza os emblemas das montadoras (PNG quadrado transparente).")
    ap.add_argument("origem", nargs="?", default=str(PASTA / "emblemas" / "novos"), help="pasta com as imagens soltas")
    ap.add_argument("--destino", default=str(PASTA / "emblemas"), help="pasta de emblemas do overlay")
    ap.add_argument("--tamanho", type=int, default=256, help="lado do quadrado em pixels (padrao 256)")
    ap.add_argument("--nao-clarear", action="store_true", help="nao trocar logos pretos por brancos")
    a = ap.parse_args(argv)
    origem, destino = Path(a.origem), Path(a.destino)
    if not origem.is_dir():
        origem.mkdir(parents=True, exist_ok=True)
        print(f"Pasta criada: {origem}\nColoque nela as imagens das montadoras e rode de novo.")
        return 0
    destino.mkdir(parents=True, exist_ok=True)
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    arquivos = sorted(f for f in origem.iterdir() if f.suffix.lower() in EXTENSOES)
    if not arquivos:
        print(f"Nenhuma imagem (PNG/JPG/WEBP/SVG) em {origem}.")
        return 0
    recortes, forcar = {}, set()
    arq_rec = origem / "recortes.json"
    if arq_rec.is_file():
        try:
            dados = json.loads(arq_rec.read_text(encoding="utf-8"))
            forcar = {slug(m) for m in dados.pop("_clarear", [])}
            recortes = {slug(k): tuple(v) for k, v in dados.items()}
        except Exception as erro:
            print(f"  AVISO: recortes.json ilegivel ({erro}); ignorado.")
    feitos = falhas = 0
    for f in arquivos:
        marca = nome_da_marca(f.name)
        img = carregar(f)
        pronto, trocou = (None, False) if img is None else preparar(img, a.tamanho, claro=not a.nao_clarear, recorte=recortes.get(marca),
                                                       forcar_claro=marca in forcar and not a.nao_clarear)
        if pronto is None:
            print(f"  FALHOU  {f.name}: nao consegui ler a imagem")
            falhas += 1
            continue
        saida = destino / f"{marca}.png"
        pronto.save(str(saida), "PNG")
        feitos += 1
        print(f"  ok      {f.name:40s} -> {saida.name}" + ("  (so o simbolo)" if marca in recortes else "") + ("  (logo escuro clareado)" if trocou else ""))
    print(f"\n{feitos} emblema(s) pronto(s) em {destino}; {falhas} falha(s). O overlay encontra os novos em ate 5 segundos.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(principal())
