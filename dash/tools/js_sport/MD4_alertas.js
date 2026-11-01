// MagicDash 4 - luzes de aviso dentro do mostrador (iRacing e LMU).
// Cada funcao devolve true/false e e usada na visibilidade do icone aceso. Sem dado do jogo = apagado (nunca inventa alerta).
var MD4A = {
    ND: "DataCorePlugin.GameData.NewData.",
    IR: "DataCorePlugin.GameRawData.Telemetry.",
    LMU: ["DataCorePlugin.GameRawData.PlayerNativeTelemetry.", "DataCorePlugin.GameRawData.CurrentPlayerTelemetry."],
    AGUA_MAX: 112.0,     // C - acima disso acende o aviso de temperatura
    OLEO_MAX: 150.0
};
function md4a_n(p) {
    var v = $prop(p);
    if (v == null || v === "") return null;
    v = Number(v);
    return isNaN(v) ? null : v;
}
function md4a_b(p) {
    var v = $prop(p);
    if (v == null || v === "") return null;
    if (v === true || v === 1 || v === "1" || String(v).toLowerCase() === "true") return true;
    return false;
}
function md4a_lmu(nome) {                    // flag do LMU na telemetria nativa (primeiro caminho que responder)
    var i, v;
    for (i = 0; i < MD4A.LMU.length; i++) {
        v = md4a_b(MD4A.LMU[i] + nome);
        if (v != null) return v;
    }
    return null;
}
function md4a_irw() {                        // iRacing: EngineWarnings (bitmask) ou null
    return md4a_n(MD4A.IR + "EngineWarnings");
}
// FAROL ligado (plugin Lovely OU telemetria nativa do LMU)
function md4a_farol() {
    if (md4a_b("LovelyPlugin.TeamLINQ.Info.HeadLights") === true) return true;
    return md4a_lmu("mHeadlights") === true;
}
// MOTOR: aviso do jogo
//  - iRacing: agua/pressao de combustivel/oleo/motor parado (EngineWarnings)
//  - LMU: superaquecimento, ou ignicao ligada com o motor parado/morto (luz de injecao do painel acesa)
function md4a_motor() {
    var w = md4a_irw();
    if (w != null && (w & 0x0E) !== 0) return true;              // 0x02 comb., 0x04 oleo, 0x08 motor parado
    var oh = md4a_lmu("mOverheating");
    if (oh === true) return true;
    if (oh !== null) {                                           // jogo = LMU (flag nativa existe)
        var ign = md4a_n(MD4A.ND + "EngineIgnitionOn"), run = md4a_n(MD4A.ND + "EngineStarted");
        if (ign != null && run != null && ign > 0 && run <= 0) return true;
        if (md4a_lmu("mDetached") === true) return true;
    }
    return false;
}
// TEMPERATURA de agua/oleo acima do limite
function md4a_temp() {
    var w = md4a_irw();
    if (w != null && (w & 0x01) !== 0) return true;              // 0x01 agua
    var a = md4a_n(MD4A.ND + "WaterTemperature"), o = md4a_n(MD4A.ND + "OilTemperature");
    if (a != null && a >= MD4A.AGUA_MAX) return true;
    if (o != null && o >= MD4A.OLEO_MAX) return true;
    return false;
}
// LIMITADOR DE PITS
function md4a_pit() {
    var v = md4a_b(MD4A.ND + "PitLimiterOn");
    if (v === true) return true;
    var w = md4a_irw();
    if (w != null && (w & 0x10) !== 0) return true;
    return md4a_lmu("mSpeedLimiter") === true;
}
// ABS / TC atuando
function md4a_abs() { var v = md4a_n(MD4A.ND + "ABSActive"); return v != null && v > 0; }
function md4a_tc() { var v = md4a_n(MD4A.ND + "TCActive"); return v != null && v > 0; }

// ---------------- POSICAO / CLASSE ----------------
// LMU: o plugin NeoRed publica a posicao na classe e a geral direto do jogo; outros jogos usam as propriedades padrao do SimHub.
function md4a_arr(path) {
    var r = $prop(path);
    if (r == null || r === "") return null;
    try { var a = JSON.parse(r); return Array.isArray(a) ? a : null; } catch (e) { return null; }
}
function md4a_idx() {                        // posicao (0-based) do piloto nas listas do plugin Lovely
    var isp = md4a_arr("LovelyPlugin.TeamLINQ.Opponents.IsPlayer");
    if (isp) { var i = isp.indexOf(true); if (i >= 0) return i; }
    var p = md4a_n(MD4A.ND + "PlayerLeaderboardPosition");
    if (p == null || p <= 0) p = md4a_n(MD4A.ND + "Position");
    return (p != null && p > 0) ? Math.round(p) - 1 : -1;
}
function md4a_pos_cls() {
    var a = md4a_arr("LovelyPlugin.TeamLINQ.Opponents.ClassPosition"), i = md4a_idx();
    if (a && i >= 0 && i < a.length) { var x = Number(a[i]); if (x > 0) return Math.round(x); }
    var v = md4a_n("NeoRedPlugin.GameInfos.PosInClass");
    if (v != null && v > 0) return Math.round(v);
    v = md4a_n(MD4A.ND + "PlayerClassPosition");
    if (v != null && v > 0) return Math.round(v);
    return null;
}
function md4a_pos_tot() {
    var v = md4a_n("NeoRedPlugin.GameInfos.PosOverall");
    if (v != null && v > 0) return Math.round(v);
    v = md4a_n(MD4A.ND + "Position");
    if (v != null && v > 0) return Math.round(v);
    return null;
}
function md4a_pos_txt() {
    var c = md4a_pos_cls(), t = md4a_pos_tot();
    if (c != null) return "P" + c;
    return t != null ? "P" + t : "P--";
}
function md4a_pos_sub() {
    var c = md4a_pos_cls(), t = md4a_pos_tot();
    return (c != null && t != null) ? "GERAL P" + t : "GERAL";
}
function md4a_cls() {
    var r = $prop("NeoRedPlugin.VehicleInfos.Class");
    if (r == null || r === "") r = $prop(MD4A.ND + "CarClass");
    return r == null ? "" : String(r);
}
