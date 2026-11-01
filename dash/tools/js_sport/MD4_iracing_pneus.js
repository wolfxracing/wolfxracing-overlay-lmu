// MagicDash 4 - pneus do iRacing em tempo real.
// Porte do EstimadorPneus do overlay_iracing (mesma fisica, mesmos limites e mesmas cores).
// O iRacing so informa temperatura/desgaste REAIS quando o carro para nos boxes; entre uma parada e outra
// este modelo estima (valor com "~"). Leitura real ao vivo aparece sem "~".
// O estado fica em root["md4p"] (texto JSON) e e atualizado no maximo a cada ~40 ms.

var MD4P = {
    G: 9.81,
    K_PROV: 3.5e-6,
    E_MIN: 1500.0,
    DESGASTE_VOLTA: 0.007,          // config.json: pneu_desgaste_volta = 0.7 (%)
    INVERTER: false,                // config.json: pneu_lado_invertido
    TEMP_MIN: 80.0,                 // config.json: pneu_temp_min
    TEMP_MAX: 105.0,                // config.json: pneu_temp_max
    SEED: { "bmwm4gt3": 1.5395436768151962e-06 },   // calibracao_pneus.json (calibrado nos boxes)
    C: ["LF", "RF", "LR", "RR"]
};

function md4p_num(k) {
    var v = $prop(k);
    if (v == null || v === "") return null;
    v = Number(v);
    return isNaN(v) ? null : v;
}
function md4p_raw(n) { return md4p_num("DataCorePlugin.GameRawData.Telemetry." + n); }
function md4p_bool(n) {
    var v = $prop("DataCorePlugin.GameRawData.Telemetry." + n);
    if (v == null) return false;
    return v === true || v === 1 || String(v).toLowerCase() === "true" || v === "1";
}

function md4p_trio(c, pre, suf, minimo) {
    var out = [];
    for (var i = 0; i < 3; i++) {
        var v = md4p_raw(c + pre + suf[i]);
        if (v == null) return null;
        out.push(v);
    }
    return Math.max(out[0], out[1], out[2]) > minimo ? out : null;
}
function md4p_mean(t) { return (t[0] + t[1] + t[2]) / 3.0; }
function md4p_same(a, b) {
    if (a == null || b == null) return a == b;
    return a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
}

function md4p_reset(S) {
    S.ancora = {}; S.ancora_real = {}; S.energia = {}; S.energia_volta = {};
    S.q = {}; S.temp = {}; S.ultima_leitura = {}; S.live = {};
    for (var i = 0; i < 4; i++) {
        var c = MD4P.C[i];
        S.ancora[c] = 1.0; S.ancora_real[c] = false; S.energia[c] = 0.0; S.energia_volta[c] = 0.0;
        S.q[c] = 0.0; S.temp[c] = null; S.ultima_leitura[c] = null; S.live[c] = null;
    }
    S.volta = null; S.volta_limpa = true;
}
function md4p_new() {
    var S = { t: null, car: null, k_real: null, n_cal: 0, k_base: null, sessao: null, temp_ult: {}, temp_mudou: {} };
    md4p_reset(S);
    for (var i = 0; i < 4; i++) { S.temp_ult[MD4P.C[i]] = null; S.temp_mudou[MD4P.C[i]] = 0; }
    return S;
}
function md4p_k(S) { return S.k_real || S.k_base || MD4P.K_PROV; }

function md4p_pesos(ay, ax) {
    var ayg = ay / MD4P.G;
    if (MD4P.INVERTER) ayg = -ayg;
    var fs = Math.min(1.0, Math.abs(ayg) / 2.5);
    var externo = 0.5 + 0.35 * fs;
    var ladoExt = ayg > 0 ? "R" : "L";
    var axg = ax / MD4P.G;
    var fb = Math.max(0.0, Math.min(1.0, -axg / 2.0));
    var fa = Math.max(0.0, Math.min(1.0, axg / 1.0));
    var frente = 0.5 + 0.2 * fb - 0.2 * fa;
    var p = {};
    for (var i = 0; i < 4; i++) {
        var c = MD4P.C[i];
        var lado = (c.charAt(0) === ladoExt) ? externo : 1.0 - externo;
        var eixo = (c.charAt(1) === "F") ? frente : 1.0 - frente;
        p[c] = 4.0 * lado * eixo;
    }
    return p;
}

function md4p_atualizar(S, dt, ativo, vel, ay, ax, tempPista) {
    if (dt <= 0 || dt > 0.5) return;
    var tp = (tempPista == null) ? 30.0 : tempPista;
    var i, c;
    for (i = 0; i < 4; i++) { c = MD4P.C[i]; if (S.temp[c] == null) S.temp[c] = tp; }
    if (!ativo || vel < 3.0) {
        for (i = 0; i < 4; i++) {
            c = MD4P.C[i];
            S.q[c] += (0.0 - S.q[c]) * Math.min(1.0, dt / 4.0);
            S.temp[c] += ((tp + 5.0) - S.temp[c]) * Math.min(1.0, dt / 60.0);
        }
        return;
    }
    var ayg = ay / MD4P.G, axg = ax / MD4P.G;
    var esforco = vel * (ayg * ayg + 0.6 * axg * axg);
    var pesos = md4p_pesos(ay, ax);
    for (i = 0; i < 4; i++) {
        c = MD4P.C[i];
        var inst = esforco * pesos[c];
        var ganho = inst * dt;
        S.energia[c] += ganho;
        S.energia_volta[c] += ganho;
        S.q[c] += (inst - S.q[c]) * Math.min(1.0, dt / 4.0);
        var alvo = tp + 25.0 + 45.0 * Math.min(1.3, S.q[c] / 40.0);
        S.temp[c] += (alvo - S.temp[c]) * Math.min(1.0, dt / 20.0);
    }
}

function md4p_fim_de_volta(S, voltaConcluida, naBox) {
    var i, c;
    if (naBox) S.volta_limpa = false;
    if (voltaConcluida == null || voltaConcluida < 0) return;
    if (S.volta == null) {
        S.volta = voltaConcluida;
        for (i = 0; i < 4; i++) S.energia_volta[MD4P.C[i]] = 0.0;
        S.volta_limpa = !naBox;
        return;
    }
    if (voltaConcluida === S.volta) return;
    S.volta = voltaConcluida;
    if (S.volta_limpa) {
        var soma = 0;
        for (i = 0; i < 4; i++) soma += S.energia_volta[MD4P.C[i]];
        var media = soma / 4.0;
        if (S.k_base == null && media > MD4P.E_MIN * 0.5) S.k_base = MD4P.DESGASTE_VOLTA / media;
    }
    for (i = 0; i < 4; i++) S.energia_volta[MD4P.C[i]] = 0.0;
    S.volta_limpa = !naBox;
}

function md4p_registrar(S, leituras) {
    var mudou = {}, ks = [], i, c, any = false;
    for (i = 0; i < 4; i++) {
        c = MD4P.C[i];
        var trio = leituras[c];
        if (!trio) continue;
        var real = md4p_mean(trio);
        var ult = S.ultima_leitura[c];
        if (ult != null && Math.abs(real - ult) < 0.003) continue;
        mudou[c] = real;
    }
    for (i = 0; i < 4; i++) {
        c = MD4P.C[i];
        if (mudou[c] === undefined) continue;
        any = true;
        var r = mudou[c];
        S.ultima_leitura[c] = r;
        if (r > S.ancora[c] + 0.10) {
            // pneu novo
        } else {
            var queda = S.ancora[c] - r;
            if (queda > 0.01 && S.energia[c] > MD4P.E_MIN) ks.push(queda / S.energia[c]);
        }
        S.ancora[c] = r; S.ancora_real[c] = true; S.energia[c] = 0.0;
    }
    if (ks.length) {
        ks.sort(function (a, b) { return a - b; });
        var novo = ks[Math.floor(ks.length / 2)];
        novo = Math.max(MD4P.K_PROV * 0.05, Math.min(MD4P.K_PROV * 30.0, novo));
        S.k_real = (!S.k_real || !S.n_cal) ? novo : 0.5 * S.k_real + 0.5 * novo;
        S.n_cal += 1;
    }
    return any;
}

// Um ciclo de atualizacao (chamado por qualquer campo; so roda de verdade 1x a cada ~40 ms).
function md4p_tick() {
    var raw = root["md4p"], S = null;
    if (raw != null && raw !== "") { try { S = JSON.parse(raw); } catch (e) { S = null; } }
    if (S == null) S = md4p_new();
    var now = (new Date()).getTime() / 1000.0;
    if (S.t != null && (now - S.t) < 0.04 && now >= S.t) return S;
    var dt = (S.t == null) ? 0.0 : now - S.t;
    S.t = now;

    var car = $prop("DataCorePlugin.GameData.CarId");
    if (car != null && car !== "" && String(car) !== S.car) {
        S.car = String(car);
        var seed = MD4P.SEED[S.car];
        S.k_real = seed ? seed : null; S.n_cal = seed ? 1 : 0; S.k_base = null;
        md4p_reset(S);
    }
    var chave = String(md4p_raw("SessionNum")) + "/" + String(md4p_raw("SessionUniqueID"));
    if (S.sessao !== chave) {
        if (S.sessao != null) {
            md4p_reset(S);
            for (var j = 0; j < 4; j++) { S.temp_ult[MD4P.C[j]] = null; S.temp_mudou[MD4P.C[j]] = 0; }
        }
        S.sessao = chave;
    }

    var vel = md4p_raw("Speed");
    if (vel == null) { var kmh = md4p_num("DataCorePlugin.GameData.NewData.SpeedKmh"); vel = (kmh == null) ? 0.0 : kmh / 3.6; }
    var naBox = md4p_bool("OnPitRoad");
    var isOn = md4p_raw("IsOnTrack");
    var naPista = (isOn == null) ? (vel > 3.0) : (isOn !== 0);
    var replay = md4p_bool("IsReplayPlaying");

    var leituras = {}, i, c;
    for (i = 0; i < 4; i++) {
        c = MD4P.C[i];
        var carcaca = md4p_trio(c, "temp", ["CL", "CM", "CR"], 1.0);
        var superficie = md4p_trio(c, "temp", ["L", "M", "R"], 1.0);
        var real = carcaca || superficie;
        if (!md4p_same(real, S.temp_ult[c])) { S.temp_ult[c] = real; S.temp_mudou[c] = now; }
        var viva = (real != null) && vel > 5.0 && (now - S.temp_mudou[c]) < 3.0;
        if (real != null && (viva || vel < 1.0)) {
            S.live[c] = md4p_mean(real);
            S.temp[c] = S.live[c];
        } else {
            S.live[c] = null;
        }
        leituras[c] = md4p_trio(c, "wear", ["L", "M", "R"], 0.0);
    }
    md4p_registrar(S, leituras);

    var ay = md4p_raw("LatAccel"), ax = md4p_raw("LongAccel");
    var ativo = naPista && !naBox && !replay;
    md4p_atualizar(S, dt, ativo, vel, ay == null ? 0.0 : ay, ax == null ? 0.0 : ax, md4p_raw("TrackTemp"));
    if (!replay) {
        var lc = md4p_raw("LapCompleted");
        md4p_fim_de_volta(S, lc == null ? -1 : Math.floor(lc), naBox);
    }
    root["md4p"] = JSON.stringify(S);
    return S;
}

// ------------------------------------------------------------------ saidas
function md4p_vida(S, c) { return Math.max(0.0, S.ancora[c] - md4p_k(S) * S.energia[c]); }
function md4p_vida_real(S, c) { return S.ancora_real[c] && S.energia[c] < MD4P.E_MIN * 0.2; }
function md4p_val_temp(S, c) { return S.live[c] != null ? S.live[c] : S.temp[c]; }

function md4p_hex(r, g, b) {
    function h(x) { var s = Math.round(x).toString(16); return s.length < 2 ? "0" + s : s; }
    return "#FF" + h(r) + h(g) + h(b);
}
function md4p_mix(c1, c2, f) {
    f = Math.max(0.0, Math.min(1.0, f));
    return [c1[0] + (c2[0] - c1[0]) * f, c1[1] + (c2[1] - c1[1]) * f, c1[2] + (c2[2] - c1[2]) * f];
}
function md4p_cor_temp(t) {
    if (t == null) return md4p_hex(90, 90, 100);
    var azul = [60, 100, 255], ciano = [60, 200, 230], verde = [60, 200, 90], amarelo = [250, 200, 40], vermelho = [235, 60, 60];
    var mn = MD4P.TEMP_MIN, mx = MD4P.TEMP_MAX, m;
    if (t < mn - 15) m = md4p_mix(azul, ciano, (t - (mn - 45)) / 30.0);
    else if (t < mn) m = md4p_mix(ciano, verde, (t - (mn - 15)) / 15.0);
    else if (t <= mx) m = verde;
    else if (t <= mx + 12) m = md4p_mix(verde, amarelo, (t - mx) / 12.0);
    else m = md4p_mix(amarelo, vermelho, (t - mx - 12) / 13.0);
    return md4p_hex(m[0], m[1], m[2]);
}
function md4p_cor_vida(v) {
    if (v == null) return md4p_hex(90, 90, 100);
    if (v >= 0.70) return md4p_hex(60, 200, 90);
    if (v >= 0.45) return md4p_hex(250, 200, 40);
    if (v >= 0.25) return md4p_hex(255, 140, 40);
    return md4p_hex(235, 60, 60);
}

// Texto da temperatura: "92" (real ao vivo) ou "~92" (estimada).
function md4_ir_temp_txt(c) {
    var S = md4p_tick();
    var v = md4p_val_temp(S, c);
    if (v == null) return "--";
    return (S.live[c] != null ? "" : "~") + Math.round(v) + "";
}
function md4_ir_temp_cor(c) {
    var S = md4p_tick();
    return md4p_cor_temp(md4p_val_temp(S, c));
}
// Vida do pneu (100 = novo): texto "~94%" (estimada) ou "94%" (real).
function md4_ir_vida_txt(c) {
    var S = md4p_tick();
    var v = md4p_vida(S, c);
    return (md4p_vida_real(S, c) ? "" : "~") + Math.round(v * 100) + "%";
}
function md4_ir_vida_val(c) {
    var S = md4p_tick();
    return md4p_vida(S, c) * 100.0;
}
function md4_ir_vida_cor(c) {
    var S = md4p_tick();
    return md4p_cor_vida(md4p_vida(S, c));
}
