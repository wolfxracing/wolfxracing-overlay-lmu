// MagicDash 4 - temperaturas de pneu e freio do Le Mans Ultimate (v2.2).
// Mesma regra do overlay LMU v1.5:
//  - FREIO: o jogo informa mBrakeTemp em KELVIN (parado nos boxes ~290-295 = ambiente). Mostramos em Celsius.
//  - PNEU : usa a camada interna (mTireInnerLayerTemperature, 3 pontos) - a media com a superficie ficou abaixo do jogo no teste real.
// Os valores sao lidos da telemetria nativa do jogo no SimHub. Como o nome exato do caminho de cada roda pode variar,
// o script testa algumas formas na primeira leitura e guarda a que funcionou (root["md4l"]).
// Se nada funcionar, usa as propriedades padrao do SimHub (TyreTemperature*, BrakeTemperature*).

var MD4L = {
    K: 273.15,
    FONTE: "interna",      // "interna" | "meio" (media superficie+interna) | "superficie"  - igual ao overlay LMU 1.5.1
    TMIN: 78.0,            // faixa ideal do pneu (verde) - ajustar se necessario
    TMAX: 100.0,
    ROOTS: ["DataCorePlugin.GameRawData.PlayerNativeTelemetry", "DataCorePlugin.GameRawData.CurrentPlayerTelemetry"],
    POS: { FL: 0, FR: 1, RL: 2, RR: 3 },
    STD: { FL: "FrontLeft", FR: "FrontRight", RL: "RearLeft", RR: "RearRight" }
};

function md4l_c(c) { return ({ LF: "FL", RF: "FR", LR: "RL" })[c] || c; }
function md4l_n(path) {
    var v = $prop(path);
    if (v == null || v === "") return null;
    v = Number(v);
    return isNaN(v) ? null : v;
}
// formas possiveis de indexar a roda i e o ponto k (0..2) de um vetor
function md4l_wform(f, i) {
    var a = String(i), b = String(i + 1);
    if (f === 0) return "mWheels[" + a + "]";
    if (f === 1) return "mWheels0" + a;
    if (f === 2) return "mWheels0" + b;
    if (f === 3) return "mWheels." + a;
    return "mWheels_" + a;
}
function md4l_eform(f, k) {
    var a = String(k), b = String(k + 1);
    if (f === 0) return "[" + a + "]";
    if (f === 1) return "0" + a;
    if (f === 2) return "0" + b;
    if (f === 3) return "." + a;
    return "_" + a;
}
function md4l_cfg() {
    var raw = root["md4l"], C = null;
    if (raw != null && raw !== "") { try { C = JSON.parse(raw); } catch (e) { C = null; } }
    var now = (new Date()).getTime() / 1000.0;
    if (C && C.ok) return C;
    if (C && (now - C.t) < 8.0) return C;          // falhou ha pouco: nao fica testando a cada quadro
    C = { ok: false, t: now, r: -1, w: -1, e: -1 };
    var r, w, e, v;
    for (r = 0; r < MD4L.ROOTS.length && C.w < 0; r++) {
        for (w = 0; w < 5; w++) {
            v = md4l_n(MD4L.ROOTS[r] + "." + md4l_wform(w, 0) + ".mBrakeTemp");
            if (v != null && v > 0) { C.r = r; C.w = w; break; }
        }
    }
    if (C.w >= 0) {
        for (e = 0; e < 5; e++) {
            v = md4l_n(MD4L.ROOTS[C.r] + "." + md4l_wform(C.w, 0) + ".mTemperature" + md4l_eform(e, 0));
            if (v != null && v > 150) { C.e = e; break; }
        }
        C.ok = true;                                 // freio achado; vetor pode ficar indisponivel (e = -1)
        if (C.e < 0) { C.ok = false; C.t = now - 4.0; C.parcial = true; }   // volta a tentar o vetor em ~4 s
    }
    root["md4l"] = JSON.stringify(C);
    return C;
}
function md4l_raw(C, c, campo) {
    c = md4l_c(c);
    if (!C || C.w < 0) return null;
    return md4l_n(MD4L.ROOTS[C.r] + "." + md4l_wform(C.w, MD4L.POS[c]) + "." + campo);
}
function md4l_vec(C, c, campo) {
    c = md4l_c(c);
    if (!C || C.w < 0 || C.e < 0) return null;
    var out = [], k, v;
    for (k = 0; k < 3; k++) {
        v = md4l_n(MD4L.ROOTS[C.r] + "." + md4l_wform(C.w, MD4L.POS[c]) + "." + campo + md4l_eform(C.e, k));
        if (v != null && v > 150) out.push(v - MD4L.K);
    }
    return out.length ? (out[0] + (out[1] == null ? out[0] : out[1]) + (out[2] == null ? out[0] : out[2])) / 3.0 : null;
}

// Temperatura do pneu em Celsius (ou null)
function md4l_tyre(c) {
    c = md4l_c(c);
    var C = md4l_cfg();
    var sup = md4l_vec(C, c, "mTemperature"), inn = md4l_vec(C, c, "mTireInnerLayerTemperature");
    var p = [];
    if (MD4L.FONTE === "superficie") { if (sup != null) p.push(sup); }
    else if (MD4L.FONTE === "meio") { if (sup != null) p.push(sup); if (inn != null) p.push(inn); }
    else { if (inn != null) p.push(inn); else if (sup != null) p.push(sup); }
    if (p.length) return p.reduce(function (a, b) { return a + b; }, 0) / p.length;
    var v = md4l_n("DataCorePlugin.GameData.NewData.TyreTemperature" + MD4L.STD[c]);   // plano B: SimHub
    if (v == null || v <= 0) return null;
    return v > 200 ? v - MD4L.K : v;
}
// Temperatura do freio em Celsius (ou null)
function md4l_brake(c) {
    c = md4l_c(c);
    var C = md4l_cfg();
    var v = md4l_raw(C, c, "mBrakeTemp");
    if (v != null && v > 0) return v - MD4L.K;
    v = md4l_n("DataCorePlugin.GameData.NewData.BrakeTemperature" + MD4L.STD[c]);       // plano B: SimHub
    if (v == null || v <= 0) return null;
    return v >= 200 ? v - MD4L.K : v;
}

function md4l_hex(r, g, b) {
    function h(x) { var s = Math.round(x).toString(16); return s.length < 2 ? "0" + s : s; }
    return "#FF" + h(r) + h(g) + h(b);
}
function md4l_mix(a, b, f) {
    f = Math.max(0.0, Math.min(1.0, f));
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}
function md4l_cor(t) {
    if (t == null) return md4l_hex(90, 90, 100);
    var azul = [60, 100, 255], ciano = [60, 200, 230], verde = [60, 200, 90], amarelo = [250, 200, 40], verm = [235, 60, 60];
    var mn = MD4L.TMIN, mx = MD4L.TMAX, m;
    if (t < mn - 15) m = md4l_mix(azul, ciano, (t - (mn - 45)) / 30.0);
    else if (t < mn) m = md4l_mix(ciano, verde, (t - (mn - 15)) / 15.0);
    else if (t <= mx) m = verde;
    else if (t <= mx + 12) m = md4l_mix(verde, amarelo, (t - mx) / 12.0);
    else m = md4l_mix(amarelo, verm, (t - mx - 12) / 13.0);
    return md4l_hex(m[0], m[1], m[2]);
}

function md4l_tyre_txt(c) { var t = md4l_tyre(c); return t == null ? "--" : Math.round(t) + ""; }
function md4l_tyre_num(c) { var t = md4l_tyre(c); return t == null ? "--" : String(Math.round(t)); }
function md4l_tyre_cor(c) { return md4l_cor(md4l_tyre(c)); }
function md4l_brake_txt(c) { var t = md4l_brake(c); return t == null ? "--" : String(Math.round(t)); }
// fonte em uso (pequeno rotulo de diagnostico na tela de pneus)
function md4l_fonte() {
    var C = md4l_cfg();
    if (C && C.w >= 0 && C.e >= 0) return "FONTE: JOGO";
    if (C && C.w >= 0) return "FONTE: JOGO (FREIO) + SIMHUB";
    return "FONTE: SIMHUB";
}
