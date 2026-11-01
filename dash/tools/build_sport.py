#!/usr/bin/env python3
"""Gera os dashes SimHub (.simhubdash) do MagicDash 4 - piloto iRacing / LMU."""
import json, uuid, zipfile, hashlib, io, os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LOGOS = '--com-logos' in sys.argv      # logos dos jogos so para uso pessoal (sao marcas registradas); o padrao publico e SEM logos
ASSETS = os.path.join(HERE, 'assets_sport')
OUT = os.path.join(HERE, 'out_sport')
os.makedirs(OUT, exist_ok=True)

T = 'SimHub.Plugins.OutputPlugins.GraphicalDash.Models.'
BH = 'SimHub.Plugins.OutputPlugins.GraphicalDash.Behaviors.Buttons.'
ND = 'DataCorePlugin.GameData.NewData.'

TEXT, GRAY = '#FFEBEBF0', '#FFAAAAB9'
GREEN, YEL, RED, ORG, BLUE = '#FF3CC85A', '#FFFAC828', '#FFEB3C3C', '#FFFF9628', '#FF6EC1FF'
GOLD = '#FFE0313F'            # acento esportivo (vermelho); mantem o nome para reaproveitar o codigo
CARD, CARDB, CELL = '#9E07080B', '#2EFFFFFF', '#17FFFFFF'
YCARD, YBORDER = '#14FAC828', '#8CFAC828'
FONT = 'Sui Generis'          # fonte esportiva inclinada (vem com o SimHub, pasta DashFonts)
SK = 0.80                     # fator de tamanho (a Sui Generis e mais larga que a Bahnschrift)


def uid(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'md4-pilot/' + seed))


# ---------------------------------------------------------------- bindings
def f_ncalc(expr):
    return {'Expression': expr}


def f_js(expr):
    return {'Interpreter': 1, 'Expression': expr}


def f_jsx(expr):
    # formula que usa funcoes do arquivo JavascriptExtensions (JSExt=1), como no Lovely Dashboard
    return {'JSExt': 1, 'Interpreter': 1, 'Expression': expr}


def b_colorf(target, formula):
    return {'Formula': formula, 'Mode': 2, 'TargetPropertyName': target}


def b_text(formula, fmt=None):
    b = {'Formula': formula, 'Mode': 2, 'TargetPropertyName': 'Text'}
    if fmt:
        b['FormatString'] = fmt
    return b


def b_value(formula):
    return {'Formula': formula, 'Mode': 2, 'TargetPropertyName': 'Value'}


def b_color(target, formula, start, end, sv, ev, mid=None, mv=None):
    return {
        'Formula': formula, 'StartColor': start, 'EnableMiddleColor': mid is not None,
        'MiddleColor': mid or '#FF000000', 'MiddleColorValue': mv if mv is not None else 1.0,
        'EndColor': end, 'StartColorValue': sv, 'EndColorValue': ev,
        'Mode': 4, 'TargetPropertyName': target,
    }


# JS helpers (strings prepended to expressions)
JS_NUM = "function n(k){var v=$prop(k); if(v==null||v===''||isNaN(Number(v))) return null; return Number(v);} "
JS_FMT = "function c(v,d){return v.toFixed(d).replace('.',',');} "


# ---------------------------------------------------------------- items
class Screen:
    def __init__(self, name, idle=False):
        self.name, self.idle, self.items, self.sid = name, idle, [], None
        self._n = 0

    def _name(self, p):
        self._n += 1
        return '%s_%02d' % (p, self._n)

    def rect(self, x, y, w, h, fill, border=None, radius=0, name=None, bind=None, skip=20):
        bs = {'BorderColor': border or '#00FFFFFF', 'CornerRadius': '%d,%d,%d,%d' % (radius,) * 4 if False else '%d,%d,%d,%d' % (radius, radius, radius, radius),
              'RadiusTopLeft': radius, 'RadiusTopRight': radius, 'RadiusBottomLeft': radius, 'RadiusBottomRight': radius}
        if border:
            bs.update({'AllBorders': 1, 'BorderTop': 1, 'BorderBottom': 1, 'BorderLeft': 1, 'BorderRight': 1})
        self.items.append({
            '$type': T + 'RectangleItem, SimHub.Plugins', 'IsRectangleItem': True,
            'BackgroundColor': fill, 'BorderStyle': bs,
            'Height': float(h), 'Left': float(x), 'Top': float(y), 'Visible': True, 'Width': float(w),
            'Name': name or self._name('rect'),
        })
        if bind:
            self.items[-1]['Bindings'] = {'BackgroundColor': bind}
            self.items[-1]['RenderingSkip'] = skip

    def text(self, x, y, w, h, txt, size, color=TEXT, bold=False, align=0, name=None,
             bind=None, color_bind=None, skip=3):
        it = {
            '$type': T + 'TextItem, SimHub.Plugins', 'IsTextItem': True,
            'Font': FONT, 'FontStyle': 'Italic', 'FontSize': (float(size) if name in ('ChevPrev', 'ChevNext') else max(11.0, round(float(size) * SK, 1))), 'FontWeight': 'Bold' if bold else 'Normal',
            'Text': txt, 'TextColor': color, 'HorizontalAlignment': align, 'VerticalAlignment': 1,
            'TextMask': '0000000000', 'BackgroundColor': '#00FFFFFF',
            'Height': float(h), 'Left': float(x), 'Top': float(y), 'Visible': True, 'Width': float(w),
            'Name': name or self._name('txt'),
        }
        bd = {}
        if bind:
            bd['Text'] = bind
            it['RenderingSkip'] = skip
        if color_bind:
            bd['TextColor'] = color_bind
            it['RenderingSkip'] = skip
        if bd:
            it['Bindings'] = bd
        self.items.append(it)

    def gauge(self, x, y, w, h, mn, mx, formula, color, bg='#14FFFFFF', align=0, color_bind=None, radius=0, name=None, skip=2):
        bd = {'Value': b_value(formula)}
        if color_bind:
            bd['GaugeColor'] = color_bind
        self.items.append({
            '$type': T + 'LinearGaugeItem, SimHub.Plugins', 'IsLinearGauge': True,
            'GaugeOrientation': 0, 'GaugeAlignment': align, 'AutoSize': False,
            'GaugeColor': color, 'AlternateGaugeColor': '#FF008000', 'UseAlternateStyle': False,
            'Minimum': float(mn), 'Maximum': float(mx), 'Value': float(mn), 'Steps': 0.0, 'PAW': float(w),
            'BackgroundColor': bg,
            'BorderStyle': {'RadiusTopLeft': radius, 'RadiusTopRight': radius, 'RadiusBottomLeft': radius, 'RadiusBottomRight': radius},
            'Height': float(h), 'Left': float(x), 'Top': float(y), 'Visible': True, 'Width': float(w),
            'Name': name or self._name('gauge'), 'RenderingSkip': skip, 'Bindings': bd,
        })

    def image(self, x, y, w, h, img, name=None):
        self.items.append({
            '$type': T + 'ImageItem, SimHub.Plugins', 'Image': img, 'AutoSize': False,
            'BackgroundColor': '#00FFFFFF', 'Height': float(h), 'Left': float(x), 'Top': float(y),
            'Visible': True, 'Width': float(w), 'Name': name or self._name('img'),
        })

    def button(self, x, y, w, h, target_sid, name):
        self.items.append({
            '$type': T + 'ButtonItem, SimHub.Plugins', 'AutoSize': False, 'SimulatedKey': 0,
            'SimulatedKeyV2': {'KeyCode': 0, 'Win': False, 'Ctrl': False, 'Alt': False, 'Shift': False},
            'SimulateKey': False, 'TriggerAction': 'None', 'TriggerSimHubInputName': '', 'TriggerControlMapperRoleName': '',
            'ButtonStyle': 0, 'IsEnabled': True, 'DisabledOpacity': 50, 'PressedOpacity': 100,
            'ChildsPositioning': 0, 'ChildsPositioningAlignment': 0, 'GroupPadding': {}, 'ChildsMargin': {},
            'ChildAlignmentHorizontal': 0, 'ChildAlignmentVertical': 0, 'BackgroundColor': '#00FFFFFF',
            'Height': float(h), 'Left': float(x), 'Top': float(y), 'Visible': True, 'BlinkPhasisInverted': False,
            'Width': float(w),
            'Behavior': {'$type': BH + 'GotoScreenBehavior, SimHub.Plugins',
                         'Settings': {'ScreenId': target_sid, 'DisableButtonIfCurrentScreen': False, 'ClearNavigationHistory': True}},
            'Name': name, 'RenderingSkip': 0, 'MinimumRefreshIntervalMS': 0.0,
        })


    def lamp(self, x, y, nome, expr, size=28):
        """luz de aviso: icone apagado sempre visivel + icone aceso por cima (Visible ligado a funcao em MD4_alertas.js)"""
        self.image(x, y, size, size, 'MD4_i_%s_off' % nome, name='Lamp_%s_off' % nome)
        self.image(x, y, size, size, 'MD4_i_%s_on' % nome, name='Lamp_%s' % nome)
        self.items[-1]['Bindings'] = {'Visible': {'Formula': f_jsx(expr), 'Mode': 2, 'TargetPropertyName': 'Visible'}}
        self.items[-1]['RenderingSkip'] = 4

    def raw(self, it):
        self.items.append(it)

    def to_json(self):
        return {
            'Name': self.name, 'InGameScreen': True, 'IdleScreen': self.idle, 'PitScreen': False,
            'ScreenId': self.sid, 'AllowOverlays': True, 'IsForegroundLayer': False, 'IsOverlayLayer': False,
            'OverlayTriggerExpression': {'Expression': ''}, 'ScreenEnabledExpression': {'Expression': ''},
            'OverlayMaxDuration': 0, 'OverlayMinDuration': 0, 'IsBackgroundLayer': False,
            'BackgroundColor': '#FF14161D', 'Items': self.items,
        }


# ---------------------------------------------------------------- shared blocks
def card(s, x, y, w, h, hot=False):
    if hot:
        s.rect(x, y, w, h, YCARD, YBORDER, 12)
    else:
        s.rect(x, y, w, h, CARD, CARDB, 12)
        s.rect(x + 10, y, 26, 3, GOLD, None, 1)          # detalhe de acento (estilo painel esportivo)


def label(s, x, y, w, txt, size=18, color=GRAY, align=0):
    s.text(x, y, w, round(size * 1.3), txt, size, color, True, align)


RPM_H = 20


def rpm_bar(s):
    s.rect(0, 0, 800, RPM_H, '#1AFFFFFF')
    P = ND + 'CarSettings_CurrentDisplayedRPMPercent'
    f = f_ncalc('[%s]' % P)
    zones = [(0, 40, GREEN), (40, 75, YEL), (75, 100, RED)]
    for lo, hi, col in zones:
        wpx = (hi - lo) * 4
        s.gauge(400 + lo * 4, 0, wpx, RPM_H, lo, hi, f, col, bg='#00FFFFFF', align=0, name='RPM_R_%d' % lo, skip=0)
        s.gauge(400 - hi * 4, 0, wpx, RPM_H, lo, hi, f, col, bg='#00FFFFFF', align=2, name='RPM_L_%d' % lo, skip=0)


def dock(s, game_tag, tabs, active, targets):
    """Cabecalho enxuto SEM barra de abas: o SimHub nao tem gesto de deslizar, entao a troca de tela
    e feita por duas grandes zonas de toque (esquerda = anterior, direita = proxima) + indicador de pagina.
    tabs: [(nome, icone)], active: indice da tela, targets: [ids das telas]"""
    n = len(tabs)
    # barra de RPM superior removida (o giro agora aparece no tacometro central)
    y0, hh = 10, 58
    s.rect(0, 0, 800, 68, '#C7080C0C')
    s.rect(0, 67, 800, 1, CARDB)
    s.text(8, y0 + 2, 56, 44, '\u2039', 44, GRAY, True, 1, name='ChevPrev')
    s.text(736, y0 + 2, 56, 44, '\u203a', 44, GRAY, True, 1, name='ChevNext')
    # logo oficial do jogo (fornecido pelo usuario), fundo transparente; altura 32 px
    if LOGOS and game_tag == 'LMU':
        s.image(66, 18, 140, 32, 'MD4_logo_lmu', name='LogoJogo')
    elif LOGOS:
        s.image(66, 18, 170, 32, 'MD4_logo_iracing', name='LogoJogo')
    else:
        # marca WolfxRacing no lugar do logo do jogo + nome do jogo em texto (para nao confundir)
        s.image(68, 4, 62, 60, 'MD4_logo_wxr', name='LogoWXR')
        s.text(134, y0 + 8, 104, 30, game_tag, 24, GOLD, True, 0, name='GameTag')
    s.text(240, y0 + 4, 320, 28, tabs[active][0].upper(), 22, TEXT, True, 1, name='ScreenTitle')
    # indicador de pagina (bolinhas)
    dx0 = 400 - (n * 16 - 8) / 2.0
    for i in range(n):
        s.rect(dx0 + i * 16, 57, 8, 8, GOLD if i == active else '#33FFFFFF', None, 4)
    # chip de bandeira
    s.rect(580, y0 + 9, 110, 30, '#FF0B0C11', CARDB, 6)
    flag_js = ("var f=String($prop('%sFlag_Name')||'').toLowerCase(); "
               "if(f.indexOf('green')>=0) return 'VERDE'; if(f.indexOf('yellow')>=0) return 'AMARELA'; "
               "if(f.indexOf('blue')>=0) return 'AZUL'; if(f.indexOf('white')>=0) return 'BRANCA'; "
               "if(f.indexOf('black')>=0) return 'PRETA'; if(f.indexOf('checker')>=0) return 'XADREZ'; "
               "if(f.indexOf('red')>=0) return 'VERMELHA'; return '--';" % ND)
    col_js = ("var f=String($prop('%sFlag_Name')||'').toLowerCase(); "
              "if(f.indexOf('yellow')>=0) return 1; if(f.indexOf('blue')>=0) return 2; "
              "if(f.indexOf('red')>=0||f.indexOf('black')>=0) return 3; return 0;" % ND)
    s.text(580, y0 + 9, 110, 30, '--', 18, GREEN, True, 1, name='FlagChip',
           bind=b_text(f_js(flag_js)),
           color_bind=b_color('TextColor', f_js(col_js), GREEN, RED, 0, 3, mid=YEL, mv=1.5), skip=10)
    # zonas de toque (por cima de tudo): anterior / proxima, com volta ao inicio
    s.button(0, y0, 300, hh, targets[(active - 1) % n], 'Toque_Anterior')
    s.button(500, y0, 300, hh, targets[(active + 1) % n], 'Toque_Proxima')


def fnum(prop, dec=0, suffix='', dflt='--', scale=''):
    return f_js(JS_NUM + JS_FMT + "var v=n('%s'); if(v==null) return '%s'; return c(v%s,%d)+'%s';" % (prop, dflt, scale, dec, suffix))


BRUSH_NS = 'http://schemas.microsoft.com/winfx/2006/xaml/presentation'


def solid(color):
    return {'SolidColorBrush': {'@xmlns': BRUSH_NS, '#text': color}}


RPMS = ND + 'Rpms'
MAXRPM = ND + 'MaxRpm'
# escala do mostrador em mil rpm (mesma formula do template AudiConcept)
DIAL_MAX = 'max(6,Ceiling([%s]/1000))' % MAXRPM

# cor do aro/marcha conforme a proximidade do limite de giro
RPM_COLOR_JS = ("var r=Number($prop('%s')), m=Number($prop('%s')); if(!(m>0)||isNaN(r)) return '#FFF2F2F6'; var k=r/m; "
                "if(k>=0.965) return '#FFFF2D2D'; if(k>=0.90) return '#FFFFB020'; if(k>=0.80) return '#FFFFE45C'; return '#FFF2F2F6';" % (RPMS, MAXRPM))
GEAR_COLOR_JS = ("var r=Number($prop('%s')), m=Number($prop('%s')); if(!(m>0)||isNaN(r)) return '#FFF2F2F6'; "
                 "return (r/m>=0.965)?'#FFFF2D2D':'#FFF2F2F6';" % (RPMS, MAXRPM))

CX, CY, OR = 400, 276, 190          # centro e raio do tacometro


def dial_item():
    """Tacometro redondo (DialGaugeItem nativo do SimHub), sem ponteiro: o valor aparece no aro (CircularGauge)."""
    cfg_off = {'ArcColor': '#00FFFFFF', 'EnableLabelColor': False, 'LabelColor': '#FFFF0000', 'EnableMajorColor': False,
               'MajorColor': '#FFFF0000', 'EnableMinorColor': False, 'MinorColor': '#FFFF0000'}
    above = dict(cfg_off, EnableLabelColor=True, LabelColor='#FFFF3B3B', EnableMajorColor=True, MajorColor='#FFFF3B3B',
                 EnableMinorColor=True, MinorColor='#FFFF3B3B')
    return {
        '$type': T + 'DialGaugeItem, SimHub.Plugins',
        'ShowRadialGauge': False, 'RadialGaugeStartOffset': 0.0, 'RadialGaugeRadius': 150.0, 'RadialGaugeThickness': 6.0,
        'RadialGaugeColor': '#FFFFFF00',
        'RangeOptimalStartValue': 0.0, 'RangeOptimalEndValue': 7.0, 'RangeIndicatorRadius': 150.0, 'RangeIndicatorThickness': 4.0,
        'BelowOptimalStyle': dict(cfg_off), 'OptimalStyle': dict(cfg_off), 'AboveOptimalStyle': above,
        'ShowNeedle': False, 'NeedleLength': 100.0, 'NeedleOffset': 0.0, 'NeedleThickness': 6.0, 'CapRadius': 0.0,
        'Value': 3.95, 'Minimum': 0.0, 'Maximum': 8.0,
        'OuterRadius': float(OR), 'InnerRadius': 0.0, 'OuterStrokeThickness': 4.0, 'InnerStrokeThickness': 0.0,
        'DialStrokeColor': solid('#FF3A3C44'), 'DialBackgroundColor': solid('#00000000'),
        'ShowDialGlassEffect': False, 'HorizontalAlignment': 1, 'VerticalAlignment': 1,
        'ScaleGlowRadius': 0.0, 'ScaleGlowColor': '#FF808080',
        'StartAngle': 135.0, 'SweepAngle': 270.0,
        'ScaleLabelStyle': {'LabelFont': FONT, 'LabelFontSize': 24.0, 'LabelFontWeight': 'Bold', 'LabelFontStyle': 'Italic',
                            'LabelColor': '#FFF2F2F6', 'LabelRadius': 128.0, 'LabelSize': '44,36'},
        'AlternateScaleLabelStyle': {'Enabled': False, 'LabelFont': 'Segoe UI', 'LabelFontSize': 20.0, 'LabelFontWeight': 'Normal',
                                     'LabelFontStyle': 'Normal', 'LabelColor': '#FFFFFFFF', 'LabelRadius': 100.0, 'LabelSize': '80,30'},
        'CustomScaleLabels': '', 'TicksPerLabel': 2.0, 'LabelCircleRotation': False, 'LabelAngleOffset': 0.0,
        'MajorTickRadius': 164.0, 'MajorDivisionsCount': 0.5, 'MajorTickColor': '#FFF2F2F6', 'MajorTickSize': '15,3',
        'MinorTickColor': '#99FFFFFF', 'MinorTickRadius': 164.0, 'MinorTickSize': '10,1', 'MinorDivisionsCount': 2.0,
        'BackgroundColor': '#00FFFFFF',
        'Height': 400.0, 'Left': float(CX - 200), 'Top': float(CY - 200), 'Visible': True, 'Width': 400.0,
        'Name': 'RPMDial', 'RenderingSkip': 0,
        'Bindings': {
            'Value': b_value(f_ncalc('isnull([%s],0)/1000' % RPMS)),
            'Maximum': {'Formula': f_ncalc(DIAL_MAX), 'Mode': 2, 'TargetPropertyName': 'Maximum'},
            'RangeOptimalEndValue': {'Formula': f_ncalc('truncate([%s]/1000)-1' % MAXRPM), 'Mode': 2, 'TargetPropertyName': 'RangeOptimalEndValue'},
        },
    }


def arc_item():
    """Aro de preenchimento do giro (CircularGaugeItem), cor muda ao se aproximar do limite."""
    return {
        '$type': T + 'CircularGaugeItem, SimHub.Plugins',
        'StrokeThickness': 10.0, 'Value': 40.0, 'Steps': 0.0, 'ValueEx': 270.0,
        'MinValue': 0.0, 'MinAngle': 225.0, 'MaxValue': 100.0, 'MaxAngle': 495.0,
        'CircleGaugeBackgroundColor': '#26FFFFFF', 'CircleGaugeColor': '#FFF2F2F6', 'BackgroundColor': '#00FFFFFF',
        'Height': 372.0, 'Left': float(CX - 186), 'Top': float(CY - 186), 'Visible': True, 'Width': 372.0,
        'Name': 'RPMArc', 'RenderingSkip': 0,
        'Bindings': {
            'Value': b_value(f_ncalc('isnull([%s],0)/(%s*1000)*100' % (RPMS, DIAL_MAX))),
            'CircleGaugeColor': b_colorf('CircleGaugeColor', f_js(RPM_COLOR_JS)),
        },
    }


def screen1(s, game, tabs, targets):
    lmu = (game == 'LMU')
    dock(s, 'LMU' if lmu else 'iRACING', tabs, 0, targets)
    # ------------- tacometro central
    s.raw(arc_item())
    s.raw(dial_item())
    s.text(CX - 60, 176, 120, 18, 'RPM x 1000', 12, GRAY, True, 1, name='RpmLbl')
    s.text(CX - 90, 196, 180, 134, '-', 124, TEXT, True, 1, name='Gear', bind=b_text(f_ncalc('[%sGear]' % ND)),
           color_bind=b_colorf('TextColor', f_js(GEAR_COLOR_JS)), skip=0)
    s.text(CX - 80, 366, 160, 56, '0', 50, TEXT, True, 1, name='Speed', bind=b_text(f_ncalc('[%sSpeedKmh]' % ND), '0'), skip=2)
    s.text(CX - 40, 420, 80, 22, 'KM/H', 15, GRAY, True, 1)

    # ------------- luzes de aviso dentro do mostrador (esq.: farol, motor, temperatura | dir.: pit, ABS, TC)
    for i, (nm, fn) in enumerate([('farol', 'md4a_farol'), ('motor', 'md4a_motor'), ('temp', 'md4a_temp')]):
        s.lamp(308, 208 + i * 42, nm, 'return %s();' % fn)
    for i, (nm, fn) in enumerate([('pit', 'md4a_pit'), ('abs', 'md4a_abs'), ('tc', 'md4a_tc')]):
        s.lamp(464, 208 + i * 42, nm, 'return %s();' % fn)

    # ------------- coluna esquerda: pneus
    card(s, 8, 76, 180, 226)
    label(s, 18, 82, 70, 'PNEUS', 13)
    label(s, 80, 83, 100, '˚C / DESG.' if lmu else '˚C / VIDA', 11, GRAY, 2)
    cells = [('DE', 'FrontLeft', 'LF'), ('DD', 'FrontRight', 'RF'), ('TE', 'RearLeft', 'LR'), ('TD', 'RearRight', 'RR')]
    for i, (lab, pos, cc) in enumerate(cells):
        cx = 13 + (i % 2) * 85
        cy = 102 + (i // 2) * 99
        s.rect(cx, cy, 81, 93, CELL, None, 8)
        s.text(cx + 7, cy + 4, 50, 16, lab, 12, GRAY, True, 0)
        if not lmu:
            s.text(cx + 1, cy + 22, 79, 36, '--', 28, GREEN, True, 1, name='TyreT_' + pos,
                   bind=b_text(f_jsx("return md4_ir_temp_txt('%s');" % cc)),
                   color_bind=b_colorf('TextColor', f_jsx("return md4_ir_temp_cor('%s');" % cc)), skip=8)
            s.gauge(cx + 8, cy + 64, 65, 7, 0, 100, f_jsx("return md4_ir_vida_val('%s');" % cc), GREEN, bg='#24FFFFFF', align=0, radius=3,
                    color_bind=b_colorf('GaugeColor', f_jsx("return md4_ir_vida_cor('%s');" % cc)), name='TyreWearBar_' + pos, skip=5)
            s.text(cx + 1, cy + 73, 79, 18, '--', 14, TEXT, True, 1, name='TyreW_' + pos,
                   bind=b_text(f_jsx("return md4_ir_vida_txt('%s');" % cc)), skip=5)
            continue
        wprop = ND + 'TyreWear' + pos
        s.text(cx + 1, cy + 22, 79, 36, '--', 28, GREEN, True, 1, name='TyreT_' + pos,
               bind=b_text(f_jsx("return md4l_tyre_txt('%s');" % cc)),
               color_bind=b_colorf('TextColor', f_jsx("return md4l_tyre_cor('%s');" % cc)), skip=8)
        s.gauge(cx + 8, cy + 64, 65, 7, 0, 100, f_ncalc('isnull([%s],0)' % wprop), GREEN, bg='#24FFFFFF', align=0, radius=3,
                color_bind=b_color('GaugeColor', f_ncalc('isnull([%s],100)' % wprop), RED, GREEN, 30.0, 85.0, mid=YEL, mv=60.0), name='TyreWearBar_' + pos, skip=10)
        s.text(cx + 1, cy + 73, 79, 18, '--', 14, TEXT, True, 1, name='TyreW_' + pos,
               bind=b_text(f_js(JS_NUM + "var v=n('%s'); if(v==null||v<=0) return '--'; return Math.round(v)+'%%';" % wprop)), skip=10)

    # ------------- coluna esquerda: combustivel / energia
    FUEL = ND + 'Fuel'
    LPL = 'DataCorePlugin.Computed.Fuel_LitersPerLap'
    EJS = ("var v=null; var ks=['DataCorePlugin.GameRawData.PlayerNativeTelemetry.mVirtualEnergy','DataCorePlugin.GameRawData.CurrentPlayerTelemetry.mVirtualEnergy']; "
           "for(var i=0;i<ks.length;i++){v=n(ks[i]); if(v!=null) break;} ")
    if lmu:
        card(s, 8, 310, 180, 158)
        label(s, 18, 316, 120, 'ENERGIA', 13)
        s.text(12, 332, 172, 48, '--', 40, GREEN, True, 0, name='Energy',
               bind=b_text(f_js(JS_NUM + EJS + "if(v==null) return '--'; v=v<=1.0001?v*100:v; return Math.round(v)+'%';")), skip=10)
        s.rect(18, 386, 160, 9, '#24FFFFFF', None, 4)
        s.gauge(18, 386, 160, 9, 0, 100, f_js(JS_NUM + EJS + "if(v==null) return 0; return v<=1.0001?v*100:v;"),
                GREEN, bg='#00FFFFFF', radius=4, name='EnergyBar', skip=10)
        s.text(18, 402, 120, 18, 'COMBUSTÍVEL', 12, GRAY, True, 0)
        s.text(12, 420, 172, 42, '--', 32, TEXT, True, 0, name='FuelL', bind=b_text(fnum(FUEL, 1, ' L')), skip=10)
    else:
        card(s, 8, 310, 180, 158, hot=True)
        label(s, 18, 316, 150, 'COMBUSTÍVEL', 13, TEXT)
        s.text(12, 334, 172, 52, '--', 42, TEXT, True, 0, name='FuelL', bind=b_text(fnum(FUEL, 1, ' L')), skip=10)
        s.rect(18, 392, 160, 9, '#24FFFFFF', None, 4)
        s.gauge(18, 392, 160, 9, 0, 100, f_ncalc('isnull([DataCorePlugin.Computed.Fuel_Percent],0)'), YEL, bg='#00FFFFFF', radius=4, name='FuelBar', skip=10)
        s.text(12, 412, 172, 40, '--', 20, YEL, True, 0, name='FuelLaps',
               bind=b_text(f_js(JS_NUM + JS_FMT + "var f=n('%s'), l=n('%s'); if(f==null||l==null||l<=0) return '--'; return '~'+c(f/l,1)+' VOLTAS';" % (FUEL, LPL))), skip=20)

    # ------------- coluna direita: delta
    card(s, 612, 76, 180, 86)
    label(s, 622, 81, 160, 'DELTA / MELHOR', 12)
    dprop = 'PersistantTrackerPlugin.SessionBestLiveDeltaSeconds'
    s.text(618, 96, 168, 46, '--', 38, GREEN, True, 1, name='Delta',
           bind=b_text(f_js(JS_NUM + "var v=n('%s'); if(v==null) return '--'; var s=v<0?'-':'+'; return s+Math.abs(v).toFixed(3).replace('.',',');" % dprop)),
           color_bind=b_color('TextColor', f_js(JS_NUM + "var v=n('%s'); if(v==null) return 0; return v>0?1:0;" % dprop), GREEN, RED, 0, 1), skip=3)
    s.rect(622, 146, 160, 8, '#24FFFFFF', None, 4)
    s.gauge(702, 146, 80, 8, 0, 1, f_js(JS_NUM + "var v=n('%s'); if(v==null) return 0; return v<0?-v:0;" % dprop), GREEN, bg='#00FFFFFF', align=0, name='DeltaFast', skip=3)
    s.gauge(622, 146, 80, 8, 0, 1, f_js(JS_NUM + "var v=n('%s'); if(v==null) return 0; return v>0?v:0;" % dprop), RED, bg='#00FFFFFF', align=2, name='DeltaSlow', skip=3)
    s.rect(701, 143, 2, 14, TEXT)

    # ------------- coluna direita: voltas
    card(s, 612, 170, 180, 100)
    rows = [('ATUAL', 'CurrentLapTime', TEXT), ('ÚLT.', 'LastLapTime', TEXT), ('MELH.', 'BestLapTime', GREEN)]
    for i, (lab, p, col) in enumerate(rows):
        yy = 175 + i * 31
        s.text(622, yy, 52, 28, lab, 12, GRAY, True, 0)
        s.text(668, yy, 118, 28, '-:--.---', 22, col, True, 2, name='Lap_' + p,
               bind=b_text(f_ncalc('[%s%s]' % (ND, p)), 'm\\:ss\\.fff'), skip=6)

    # ------------- coluna direita: posicao
    card(s, 612, 278, 180, 118)
    label(s, 622, 283, 70, 'POSIÇÃO', 12)
    CLS = ND + 'CarClass'
    if lmu:
        cls_norm = "var r=md4a_cls(); var c=r.toLowerCase().replace(/[^a-z0-9]/g,''); "
        cls_txt = (cls_norm + "if(!c) return '--'; if(c.indexOf('hyper')>=0) return 'HYPERCAR'; if(c.indexOf('gt3')>=0) return 'LMGT3'; "
                   "if(c.indexOf('lmp2')>=0) return 'LMP2'; if(c.indexOf('lmp3')>=0) return 'LMP3'; if(c.indexOf('lmp1')>=0) return 'LMP1'; "
                   "if(c.indexOf('gte')>=0) return 'GTE'; return r.toUpperCase().substring(0,10);")
        cls_cor = (cls_norm + "if(c.indexOf('hyper')>=0) return '#FFE63C28'; if(c.indexOf('gt3')>=0) return '#FF229900'; "
                   "if(c.indexOf('lmp2')>=0) return '#FF0088FF'; if(c.indexOf('lmp3')>=0) return '#FF880088'; if(c.indexOf('lmp1')>=0) return '#FFFF00AA'; "
                   "if(c.indexOf('gte')>=0) return '#FF00CC44'; if(!c) return '#FF5A5A64'; return '#FF6E6E7A';")
        s.rect(696, 283, 88, 18, '#FF5A5A64', None, 5, name='ClassChipBg', bind=b_colorf('BackgroundColor', f_jsx(cls_cor)))
        s.text(696, 283, 88, 18, '--', 11, '#FFFFFFFF', True, 1, name='ClassChip', bind=b_text(f_jsx(cls_txt)), skip=20)
    s.text(620, 302, 104, 62, 'P-', 54, TEXT, True, 0, name='Pos', bind=b_text(f_jsx("return md4a_pos_txt();")), skip=10)
    s.text(704, 330, 80, 22, 'GERAL', 12, GRAY, True, 2, name='ClassPos', bind=b_text(f_jsx("return md4a_pos_sub();")), skip=10)
    s.text(622, 366, 164, 24, 'VOLTA --', 16, GRAY, True, 0, name='LapOf',
           bind=b_text(f_js(JS_NUM + "var l=n('%sCurrentLap'), t=n('%sTotalLaps'); if(l==null) return 'VOLTA --'; return 'VOLTA '+Math.round(l)+((t&&t>0&&t<9999)?' / '+Math.round(t):'');" % (ND, ND))), skip=20)

    # ------------- coluna direita: ajustes
    card(s, 612, 404, 180, 64)
    adj = [('TC', 'TCLevel', 0), ('ABS', 'ABSLevel', 0), ('BB', 'BrakeBias', 1)]
    for i, (lab, p, dec) in enumerate(adj):
        cx = 616 + i * 59
        s.text(cx, 408, 56, 14, lab, 11, GRAY, True, 1)
        s.text(cx, 422, 56, 42, '--', 28 if lab != 'BB' else 24, TEXT, True, 1, name='Adj_' + lab,
               bind=b_text(fnum(ND + p, dec)), skip=10)


def screen_ir_estrategia(s, tabs, targets):
    dock(s, 'iRACING', tabs, 1, targets)
    FUEL, MAXF = ND + 'Fuel', ND + 'MaxFuel'
    LPL = 'DataCorePlugin.Computed.Fuel_LitersPerLap'
    card(s, 20, 80, 300, 330)
    label(s, 34, 88, 200, 'COMBUSTÍVEL', 20)
    s.text(30, 130, 280, 130, '--', 100, TEXT, True, 0, name='Fuel', bind=b_text(fnum(FUEL, 1)), skip=5)
    s.text(34, 270, 60, 40, 'L', 32, GRAY, True, 0)
    s.rect(34, 330, 272, 22, '#24FFFFFF', None, 11)
    s.gauge(34, 330, 272, 22, 0, 100, f_js(JS_NUM + "var f=n('%s'), m=n('%s'); if(f==null||!m) return 0; return 100*f/m;" % (FUEL, MAXF)), GREEN, bg='#00FFFFFF', radius=11, name='FuelBar', skip=10)
    s.text(34, 366, 270, 30, '--', 22, GRAY, True, 0, name='Tank', bind=b_text(f_js(JS_NUM + JS_FMT + "var m=n('%s'); return m==null?'--':'TANQUE '+c(m,1)+' L';" % MAXF)), skip=30)
    cells = [
        ('CONSUMO MÉDIO', f_js(JS_NUM + JS_FMT + "var l=n('%s'); return l==null||l<=0?'--':'~'+c(l,2);" % LPL), 'L/v', TEXT),
        ('VOLTAS RESTANTES', f_js(JS_NUM + JS_FMT + "var f=n('%s'), l=n('%s'); return (f==null||l==null||l<=0)?'--':'~'+c(f/l,1);" % (FUEL, LPL)), 'v', YEL),
        ('FIM DA CORRIDA', f_js(JS_NUM + "var t=n('%sTotalLaps'), l=n('%sCurrentLap'); if(t==null||l==null||t<=0||t>=9999) return '--'; return Math.max(0,Math.round(t-l+1));" % (ND, ND)), 'v', TEXT),
        ('ABASTECER P/ TERMINAR', f_js(JS_NUM + JS_FMT + "var t=n('%sTotalLaps'), l=n('%sCurrentLap'), p=n('%s'), f=n('%s'); if(t==null||l==null||p==null||f==null||p<=0||t<=0||t>=9999) return '--'; var need=(t-l+1)*p-f; return need<=0?'0,0':'~'+c(need,1);" % (ND, ND, LPL, FUEL)), 'L', YEL),
    ]
    for i, (lab, fm, unit, col) in enumerate(cells):
        cx = 330 + (i % 2) * 227
        cy = 80 + (i // 2) * 168
        card(s, cx, cy, 217, 162, hot=(i == 3))
        label(s, cx + 12, cy + 8, 195, lab, 16)
        s.text(cx + 8, cy + 56, 150, 72, '--', 50, col, True, 0, name='Est_%d' % i, bind=b_text(fm), skip=20)
        s.text(cx + 158, cy + 92, 50, 30, unit, 22, GRAY, True, 0)
    # barra de situação
    card(s, 20, 420, 760, 48, hot=True)
    s.text(34, 424, 330, 40, '--', 26, YEL, True, 0, name='Stops',
           bind=b_text(f_js(JS_NUM + "var t=n('%sTotalLaps'), l=n('%sCurrentLap'), p=n('%s'), f=n('%s'), m=n('%s'); if(t==null||l==null||p==null||f==null||!m||p<=0||t<=0||t>=9999) return '--'; var need=(t-l+1)*p-f; if(need<=0) return 'SEM PARADA'; return '~'+Math.ceil(need/m)+' PARADA(S)';" % (ND, ND, LPL, FUEL, MAXF))), skip=30)
    s.text(420, 424, 350, 40, 'ESTIMATIVA PELO CONSUMO MÉDIO', 18, GRAY, True, 2)


def screen_ir_sessao(s, tabs, targets):
    dock(s, 'iRACING', tabs, 2, targets)
    card(s, 20, 80, 340, 160)
    label(s, 34, 88, 300, 'TEMPO RESTANTE', 20)
    s.text(28, 134, 330, 90, '--:--', 78, TEXT, True, 0, name='TimeLeft',
           bind=b_text(f_ncalc('[%sSessionTimeLeft]' % ND), 'h\\:mm\\:ss'), skip=5)
    card(s, 370, 80, 210, 160)
    label(s, 384, 88, 180, 'VOLTA', 20)
    s.text(380, 140, 195, 80, '--', 50, TEXT, True, 0, name='LapBig',
           bind=b_text(f_js(JS_NUM + "var l=n('%sCurrentLap'), t=n('%sTotalLaps'); if(l==null) return '--'; return Math.round(l)+((t&&t>0&&t<9999)?' / '+Math.round(t):'');" % (ND, ND))), skip=20)
    card(s, 590, 80, 190, 160)
    label(s, 604, 88, 170, 'INCIDENTES', 20)
    inc = 'DataCorePlugin.GameRawData.Telemetry.PlayerCarMyIncidentCount'
    s.text(600, 130, 170, 100, '--', 72, YEL, True, 0, name='Incidents',
           bind=b_text(f_js(JS_NUM + "var v=n('%s'); return v==null?'--':Math.round(v)+'x';" % inc)), skip=30)
    for i, (lab, who, gap, hot) in enumerate([('À FRENTE', 'DriverAhead_00_Name', 'DriverAhead_00_Gap', False),
                                              ('ATRÁS', 'DriverBehind_00_Name', 'DriverBehind_00_Gap', True)]):
        cx = 20 + i * 390
        if hot:
            s.rect(cx, 250, 380, 218, '#1AFF9628', '#99FF9628', 12)
        else:
            card(s, cx, 250, 380, 218)
        label(s, cx + 14, 258, 120, lab, 20, TEXT if hot else GRAY)
        s.text(cx + 130, 256, 240, 34, '--', 26, TEXT, True, 2, name='Who_%d' % i,
               bind=b_text(f_js("var v=$prop('PersistantTrackerPlugin.%s'); return (v==null||v==='')?'--':String(v).toUpperCase();" % who)), skip=30)
        s.text(cx + 10, 320, 300, 110, '--', 84, ORG if hot else TEXT, True, 0, name='Gap_%d' % i,
               bind=b_text(f_js(JS_NUM + JS_FMT + "var v=n('PersistantTrackerPlugin.%s'); if(v==null) return '--'; return %sc(Math.abs(v),2);" % (gap, "'+'+" if not hot else ''))), skip=10)
        s.text(cx + 310, 372, 60, 40, 's', 28, GRAY, True, 0)


def screen_lmu_energia(s, tabs, targets):
    dock(s, 'LMU', tabs, 1, targets)
    FUEL, MAXF = ND + 'Fuel', ND + 'MaxFuel'
    LPL = 'DataCorePlugin.Computed.Fuel_LitersPerLap'
    EJS = ("var v=null; var ks=['DataCorePlugin.GameRawData.PlayerNativeTelemetry.mVirtualEnergy','DataCorePlugin.GameRawData.CurrentPlayerTelemetry.mVirtualEnergy']; "
           "for(var i=0;i<ks.length;i++){v=n(ks[i]); if(v!=null) break;} ")
    card(s, 20, 80, 375, 200, hot=True)
    label(s, 34, 88, 250, 'ENERGIA VIRTUAL', 20, TEXT)
    s.text(30, 126, 355, 100, '--', 92, TEXT, True, 0, name='Energy',
           bind=b_text(f_js(JS_NUM + EJS + "if(v==null) return '--'; v=v<=1.0001?v*100:v; return v.toFixed(1).replace('.',',')+'%';")), skip=5)
    s.rect(34, 244, 347, 22, '#24FFFFFF', None, 11)
    s.gauge(34, 244, 347, 22, 0, 100, f_js(JS_NUM + EJS + "if(v==null) return 0; return v<=1.0001?v*100:v;"), YEL, bg='#00FFFFFF', radius=11, name='EnergyBar', skip=10)
    card(s, 405, 80, 375, 200)
    label(s, 419, 88, 250, 'COMBUSTÍVEL', 20)
    s.text(415, 126, 355, 100, '--', 92, TEXT, True, 0, name='Fuel', bind=b_text(fnum(FUEL, 1, ' L')), skip=5)
    s.rect(419, 244, 347, 22, '#24FFFFFF', None, 11)
    s.gauge(419, 244, 347, 22, 0, 100, f_js(JS_NUM + "var f=n('%s'), m=n('%s'); if(f==null||!m) return 0; return 100*f/m;" % (FUEL, MAXF)), GREEN, bg='#00FFFFFF', radius=11, name='FuelBar', skip=10)
    cells = [
        ('CONSUMO COMBUSTÍVEL', f_js(JS_NUM + JS_FMT + "var l=n('%s'); return l==null||l<=0?'--':'~'+c(l,2);" % LPL), 'L/v', TEXT),
        ('ALCANCE COMBUSTÍVEL', f_js(JS_NUM + JS_FMT + "var f=n('%s'), l=n('%s'); return (f==null||l==null||l<=0)?'--':'~'+c(f/l,1);" % (FUEL, LPL)), 'v', YEL),
        ('TANQUE', f_js(JS_NUM + JS_FMT + "var m=n('%s'); return m==null?'--':c(m,1);" % MAXF), 'L', TEXT),
    ]
    for i, (lab, fm, unit, col) in enumerate(cells):
        cx = 20 + i * 255
        card(s, cx, 290, 250, 120)
        label(s, cx + 12, 296, 230, lab, 16)
        s.text(cx + 8, 330, 170, 66, '--', 44, col, True, 0, name='En_%d' % i, bind=b_text(fm), skip=20)
        s.text(cx + 178, 352, 60, 30, unit, 22, GRAY, True, 0)
    card(s, 20, 420, 760, 48, hot=True)
    s.text(34, 424, 400, 40, 'VALORES ~ = CALCULADOS', 22, YEL, True, 0)
    s.text(420, 424, 350, 40, 'ENERGIA: DADO DO JOGO', 18, GRAY, True, 2)


def screen_lmu_pneus(s, tabs, targets):
    dock(s, 'LMU', tabs, 2, targets)
    cells = [('DIANT. ESQ.', 'FrontLeft'), ('DIANT. DIR.', 'FrontRight'), ('TRAS. ESQ.', 'RearLeft'), ('TRAS. DIR.', 'RearRight')]
    for i, (lab, pos) in enumerate(cells):
        cx = 20 + (i % 2) * 245
        cy = 80 + (i // 2) * 194
        card(s, cx, cy, 235, 184)
        label(s, cx + 12, cy + 8, 200, lab, 18)
        tprop, pprop, wprop = ND + 'TyreTemperature' + pos, ND + 'TyrePressure' + pos, ND + 'TyreWear' + pos
        cc = {'FrontLeft': 'FL', 'FrontRight': 'FR', 'RearLeft': 'RL', 'RearRight': 'RR'}[pos]
        s.text(cx + 8, cy + 34, 140, 66, '--', 56, GREEN, True, 0, name='T_' + pos,
               bind=b_text(f_jsx("return md4l_tyre_num('%s');" % cc)),
               color_bind=b_colorf('TextColor', f_jsx("return md4l_tyre_cor('%s');" % cc)), skip=8)
        s.text(cx + 140, cy + 52, 80, 30, '˚C', 22, GRAY, True, 0)
        s.text(cx + 12, cy + 104, 210, 28, '--', 22, TEXT, True, 0, name='P_' + pos,
               bind=b_text(f_js(JS_NUM + "var v=n('%s'); if(v==null||v<=0) return '--'; return Math.round(v)+' '+String($prop('%sTyrePressureUnit')||'');" % (pprop, ND))), skip=10)
        s.rect(cx + 12, cy + 146, 150, 14, '#24FFFFFF', None, 7)
        s.gauge(cx + 12, cy + 146, 150, 14, 0, 100, f_ncalc('isnull([%s],0)' % wprop), GREEN, bg='#00FFFFFF', radius=7,
                color_bind=b_color('GaugeColor', f_ncalc('isnull([%s],100)' % wprop), RED, GREEN, 30.0, 85.0, mid=YEL, mv=60.0), name='W_' + pos, skip=10)
        s.text(cx + 168, cy + 140, 62, 26, '--', 20, TEXT, True, 2, name='Wp_' + pos,
               bind=b_text(f_js(JS_NUM + "var v=n('%s'); if(v==null||v<=0) return '--'; return Math.round(v)+'%%';" % wprop)), skip=10)
    s.text(420, 468, 372, 12, '', 10, '#FF6E6E7A', True, 2, name='FonteTemp',
           bind=b_text(f_jsx("return md4l_fonte();")), skip=60)
    # freios + óleo/água
    card(s, 510, 80, 270, 235)
    label(s, 524, 88, 200, 'FREIOS ˚C', 18)
    for i, pos in enumerate(['FrontLeft', 'FrontRight', 'RearLeft', 'RearRight']):
        bx = 520 + (i % 2) * 125
        by = 128 + (i // 2) * 90
        cc = {'FrontLeft': 'FL', 'FrontRight': 'FR', 'RearLeft': 'RL', 'RearRight': 'RR'}[pos]
        s.text(bx, by, 120, 50, '--', 40, TEXT, True, 0, name='B_' + pos,
               bind=b_text(f_jsx("return md4l_brake_txt('%s');" % cc)), skip=8)
    card(s, 510, 325, 270, 143)
    for i, (lab, p) in enumerate([('ÓLEO', 'OilTemperature'), ('ÁGUA', 'WaterTemperature')]):
        yy = 340 + i * 62
        s.text(524, yy, 100, 40, lab, 20, GRAY, True, 0)
        s.text(600, yy - 4, 170, 52, '--', 40, TEXT, True, 2, name='Tmp_' + p,
               bind=b_text(f_js(JS_NUM + "var v=n('%s%s'); if(v==null||v<=0) return '--'; return Math.round(v)+' ˚C';" % (ND, p))), skip=20)


# ---------------------------------------------------------------- packaging
ICONS = ['gauge', 'fuel', 'flag', 'bolt', 'tire']


def build(dname, title, game, screens_spec, tabs, js_files=()):
    names = [t[0] for t in tabs]
    scr = [Screen(n, idle=(i == 0)) for i, n in enumerate(names)]
    for i, s in enumerate(scr):
        s.sid = uid(dname + '/' + names[i])
    targets = [s.sid for s in scr]
    for si, (s, fn) in enumerate(zip(scr, screens_spec)):
        fn(s, tabs, targets)
        s.items.insert(0, {
            '$type': T + 'ImageItem, SimHub.Plugins', 'Image': 'MD4_bg' if si == 0 else 'MD4_bg2', 'AutoSize': False,
            'BackgroundColor': '#00FFFFFF', 'Height': 480.0, 'Left': 0.0, 'Top': 0.0, 'Visible': True, 'Width': 800.0, 'Name': 'Fundo'})
    # recursos de imagem
    res = io.BytesIO()
    images = []
    zr = zipfile.ZipFile(res, 'w', zipfile.ZIP_DEFLATED)
    for fn in sorted(os.listdir(ASSETS)):
        if fn.startswith('MD4_ic_') or (fn.startswith('MD4_logo_') and fn != 'MD4_logo_wxr.png' and not LOGOS):
            continue          # icones da barra de abas (removida)
        data = open(os.path.join(ASSETS, fn), 'rb').read()
        im = Image.open(io.BytesIO(data))
        zr.writestr(fn, data)
        images.append({'Name': fn[:-4], 'Extension': '.png', 'Modified': False, 'Optimized': True,
                       'Width': im.width, 'Height': im.height, 'Length': len(data), 'MD5': hashlib.md5(data).hexdigest()})
    zr.close()
    meta = {
        'Category': 'MagicDash4', 'Title': title, 'Description': 'MagicDash 4 (800x480) - painel esportivo estilo cluster: tacometro central, luzes de aviso, pneus, combustivel/energia, delta e posicao.',
        'Author': 'WolfxRacing', 'ScreenCount': float(len(scr)), 'InGameScreensIndexs': list(range(len(scr))),
        'IdleScreensIndexs': [0], 'MainPreviewIndex': 0, 'IsOverlay': False, 'Width': 800.0, 'Height': 480.0,
        'OverlaySizeWarning': False, 'MetadataVersion': 2.0, 'EnableOnDashboardMessaging': False,
        'PitScreensIndexs': [], 'SimHubVersion': '9.13.3', 'DashboardVersion': '1.0.0',
    }
    dash = {
        'DashboardDebugManager': {'Maximized': False}, 'Version': 2, 'Id': uid(dname), 'BaseHeight': 480, 'BaseWidth': 800,
        'BackgroundColor': '#FF14161D', 'Screens': [s.to_json() for s in scr], 'SnapToGrid': False, 'HideLabels': True,
        'ShowForeground': True, 'ForegroundOpacity': 100.0, 'ShowBackground': True, 'BackgroundOpacity': 100.0,
        'ShowBoundingRectangles': True, 'GridSize': 10, 'Images': images, 'Metadata': meta,
        'ShowOnScreenControls': False, 'IsOverlay': False, 'EnableClickThroughOverlay': False, 'EnableOnDashboardMessaging': False,
        'UseStrictJSIsolation': False, 'UseStrictJSIsolationWarning': True,
    }
    # miniatura simples (o SimHub gera a oficial ao salvar)
    tag = 'ir' if 'iRacing' in dname else 'lmu'
    def thumb_bytes(i):
        fp = os.path.join(HERE, 'thumbs', '%s_%d.png' % (tag, i))
        im = Image.open(fp if os.path.exists(fp) else os.path.join(ASSETS, 'MD4_bg.png')).convert('RGB')
        bio = io.BytesIO(); im.save(bio, 'PNG', optimize=True); return bio.getvalue()
    path = os.path.join(OUT, dname + '.simhubdash')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        base = dname + '\\' + dname
        z.writestr(base + '.djson', json.dumps(dash, ensure_ascii=False, indent=1))
        z.writestr(base + '.djson.metadata', json.dumps(meta, indent=2))
        z.writestr(base + '.djson.png', thumb_bytes(0))
        for i in range(len(scr)):
            z.writestr(base + '.djson.%02d.png' % i, thumb_bytes(i))
        z.writestr(base + '.djson.ressources', res.getvalue())
        for jf in js_files:
            z.writestr(dname + '\\JavascriptExtensions\\' + os.path.basename(jf), open(jf, 'rb').read())
    with open(os.path.join(OUT, dname + '.djson'), 'w', encoding='utf-8') as f:
        json.dump(dash, f, ensure_ascii=False, indent=1)
    return path, dash


IR_TABS = [('Corrida', 'gauge'), ('Estratégia', 'fuel'), ('Sessão', 'flag')]
LMU_TABS = [('Corrida', 'gauge'), ('Energia', 'bolt'), ('Pneus', 'tire')]

if __name__ == '__main__':
    # uso:  python build_sport.py [--so iracing|lmu|todos] [--com-logos]
    SO = sys.argv[sys.argv.index('--so') + 1].lower() if '--so' in sys.argv else 'todos'
    JS = lambda *n: [os.path.join(HERE, 'js_sport', x) for x in n]
    feitos = []
    if SO in ('todos', 'iracing'):
        feitos.append(build('MagicDash4 iRacing Sport', 'MagicDash4 iRacing Sport', 'iRacing',
                            [lambda s, t, g: screen1(s, 'iRacing', t, g), screen_ir_estrategia, screen_ir_sessao], IR_TABS,
                            js_files=JS('MD4_iracing_pneus.js', 'MD4_alertas.js')))
    if SO in ('todos', 'lmu'):
        feitos.append(build('MagicDash4 LMU Sport', 'MagicDash4 LMU Sport', 'LMU',
                            [lambda s, t, g: screen1(s, 'LMU', t, g), screen_lmu_energia, screen_lmu_pneus], LMU_TABS,
                            js_files=JS('MD4_lmu_temps.js', 'MD4_alertas.js')))
    for p, d in feitos:
        print(p, os.path.getsize(p), [len(s['Items']) for s in d['Screens']])
