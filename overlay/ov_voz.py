# -*- coding: utf-8 -*-
"""
Avisos por voz do coach (v1.7). A DECISAO do que falar e logica pura (testavel); a fala em si usa a voz do Windows (SAPI,
via um PowerShell persistente) e e opcional: desligada por padrao. Falha da voz nunca derruba o overlay.

Regras para nao poluir: no maximo uma frase a cada 2 s; cada curva e anunciada uma vez por volta; so avalia por voz as freadas
com problema (e elogia a perfeita de vez em quando); nada de fala com o carro parado nos boxes.
"""
import math
import subprocess
import sys

INTERVALO_MIN_S = 2.0
ANUNCIO_M = 230.0                 # anuncia a curva quando a freada esta a ate esta distancia
ELOGIO_A_CADA = 4                 # a cada N freadas perfeitas, uma e elogiada

_SCRIPT = (
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Rate=2;"
    "try{$s.SelectVoiceByHints('NotSet','NotSet',0,[Globalization.CultureInfo]'pt-BR')}catch{};"
    "while(($l=[Console]::In.ReadLine()) -ne $null){if($l -eq '!cancel'){$s.SpeakAsyncCancelAll()}else{[void]$s.SpeakAsync($l)}}"
)

_NOTAS_FALA = {"cedo": "freou cedo", "muito_cedo": "freou muito cedo", "tarde": "freou tarde", "muito_tarde": "freou muito tarde",
               "perfeita": "freada perfeita", "boa": "boa freada",
               "sem_tirada": "nao tirou o pe", "freou_em_vez": "freou onde bastava tirar o pe"}


class FalaWindows:
    """Backend de voz. Mantem um PowerShell vivo e manda uma frase por linha."""

    def __init__(self):
        self._proc = None
        self.erro = None

    def iniciar(self):
        if self._proc is not None or not sys.platform.startswith("win"):
            return self._proc is not None
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
                                          stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          creationflags=flags)
            return True
        except Exception as e:
            self.erro = e.__class__.__name__
            self._proc = None
            return False

    def falar(self, texto):
        if self._proc is None and not self.iniciar():
            return False
        try:
            self._proc.stdin.write((texto.replace("\n", " ") + "\n").encode("utf-8"))
            self._proc.stdin.flush()
            return True
        except Exception as e:
            self.erro = e.__class__.__name__
            self.parar()
            return False

    def cancelar(self):
        self.falar("!cancel")

    def parar(self):
        p, self._proc = self._proc, None
        if p is not None:
            try:
                p.stdin.close()
                p.terminate()
            except Exception:
                pass


class Locutor:
    """Decide o que falar a partir do resumo do Coach (e do coach de ritmo). falar_fn(texto) -> bool."""

    def __init__(self, falar_fn, relogio):
        self.falar_fn = falar_fn
        self.relogio = relogio
        self.ativo = False
        self._ult_fala = -1e9
        self._anunciada = None               # (n) ja anunciada nesta aproximacao
        self._ult_dist = None
        self._ult_feedback = None
        self._perfeitas = 0
        self._ult_resumo_volta = None
        self._ult_aviso_comb = None

    def _dizer(self, texto, prioridade=False):
        agora = self.relogio()
        if not self.ativo:
            return False
        if not prioridade and agora - self._ult_fala < INTERVALO_MIN_S:
            return False
        ok = False
        try:
            ok = bool(self.falar_fn(texto))
        except Exception:
            ok = False
        if ok:
            self._ult_fala = agora
        return ok

    def processar(self, coach, ritmo=None, no_carro=True):
        """Chamar a cada ciclo com o resumo do coach. Devolve a frase falada (ou None)."""
        if not self.ativo or not coach or coach.get("estado") != "ok" or not no_carro:
            return None
        falou = None
        pr = coach.get("proxima")
        if pr:
            if self._ult_dist is not None and pr["dist_m"] > self._ult_dist + 300.0:
                self._anunciada = None                          # voltou a cruzar a linha: nova volta
            self._ult_dist = pr["dist_m"]
            if pr["dist_m"] <= ANUNCIO_M and self._anunciada != (pr["n"], pr["total"]) and pr.get("fase") != "freando":
                marcha = f" marcha {pr['marcha']}" if pr.get("marcha") else ""
                frase = f"Curva {pr['n']},{marcha}" + (", tire o pe" if pr.get("tipo") == "tirada" else "")
                if self._dizer(frase):
                    self._anunciada = (pr["n"], pr["total"])
                    falou = frase
        fb = coach.get("feedback")
        if fb and fb is not self._ult_feedback:                # o Coach cria um dict novo a cada curva avaliada
            self._ult_feedback = fb
            nota = fb.get("nota")
            if nota in ("perfeita", "boa"):
                self._perfeitas += 1
                if nota == "perfeita" and self._perfeitas % ELOGIO_A_CADA == 0:
                    frase = f"Curva {fb['n']}, " + ("tirada perfeita" if fb.get("tipo") == "tirada" else "freada perfeita")
                    if self._dizer(frase):
                        falou = frase
            elif nota in _NOTAS_FALA:
                m = f", {abs(fb['freada_m']):.0f} metros" if fb.get("freada_m") is not None else ""
                nome = _NOTAS_FALA[nota]
                if fb.get("tipo") == "tirada":
                    nome = nome.replace("freou muito", "tirou o pe muito").replace("freou", "tirou o pe") if nota in ("cedo", "muito_cedo", "tarde", "muito_tarde") else nome
                frase = f"Curva {fb['n']}, {nome}{m}"
                if self._dizer(frase):
                    falou = frase
        rv = coach.get("resumo_volta")
        if rv is not None and rv is not self._ult_resumo_volta:
            self._ult_resumo_volta = rv
            if rv.get("pior"):
                frase = f"Volta fechada. Pior curva, {rv['pior']['n']}"
                if self._dizer(frase, prioridade=False):
                    falou = frase
        c = (ritmo or {}).get("combustivel")
        if c and c.get("estado") in ("poupar", "parada"):
            chave = (c["estado"], round(c["poupar_pct"]))
            if chave != self._ult_aviso_comb:
                frase = (f"Poupe {math.ceil(c['poupar_pct'] - 1e-9)} por cento de combustivel por volta" if c["estado"] == "poupar"
                         else "Combustivel pede parada")
                if self._dizer(frase):
                    self._ult_aviso_comb = chave
                    falou = frase
        return falou
