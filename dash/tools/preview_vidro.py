import json,asyncio,base64,glob,os,sys
from playwright.async_api import async_playwright
SAMPLE={'RpmLbl':'RPM x 1000','Gear':'4','Speed':'187','Delta':'−0,214','Lap_CurrentLapTime':'1:42.318','Lap_LastLapTime':'1:42.905','Lap_BestLapTime':'1:42.102',
 'Pos':'P7','ClassPos':'CL. P3','LapOf':'VOLTA 12 / 30','Adj_TC':'3','Adj_ABS':'2','Adj_BB':'56,5','FuelL':'42,6 L','FuelLaps':'~8,4 VOLTAS','Energy':'61%',
 'FlagChip':'VERDE','ClassChip':'HYPERCAR','Fuel':'42,6','Tank':'TANQUE 60,0 L','TimeLeft':'0:27:40','LapBig':'12 / 30','Incidents':'4x','Who_0':'#14 A. SILVA','Who_1':'#33 M. COSTA','Gap_0':'+1,82','Gap_1':'0,64'}
def sample(n,default):
    if n in SAMPLE: return SAMPLE[n]
    if n.startswith('TyreT_') or n.startswith('T_'): return {'FrontLeft':'92','FrontRight':'96','RearLeft':'104','RearRight':'99'}[n.split('_')[1]]+('' if n.startswith('TyreT_') else '')
    if n.startswith('TyreW_') or n.startswith('Wp_'): return '94%'
    if n.startswith('P_'): return '152 kPa'
    if n.startswith('B_'): return '412'
    if n.startswith('Tmp_'): return '98 ˚C'
    if n.startswith('Est_'): return ['~2,84','~15,0','18','~17,4'][int(n[-1])]
    if n.startswith('En_'): return ['~2,67','~22,9','60,0'][int(n[-1])]
    if n=='Stops': return '~1 PARADA(S)'
    return default
def html(scr,imgs):
    import base64 as _b
    _f=_b.b64encode(open('/mnt/user-data/uploads/SimHub/DashFonts/SUIGBI_.TTF','rb').read()).decode()
    o=['<html><head><style>@font-face{font-family:"Sui Generis";src:url(data:font/ttf;base64,'+_f+');font-weight:700;font-style:italic}</style></head><body style="margin:0;background:#000"><div style="position:relative;width:800px;height:480px;overflow:hidden;font-family:\'Sui Generis\',sans-serif;font-style:italic">']
    for it in scr['Items']:
        t=it['$type'].split(',')[0].split('.')[-1]
        st=f"position:absolute;left:{it['Left']}px;top:{it['Top']}px;width:{it['Width']}px;height:{it['Height']}px;box-sizing:border-box;"
        def c(a):
            a=a.lstrip('#'); 
            if len(a)==8: return f"rgba({int(a[2:4],16)},{int(a[4:6],16)},{int(a[6:8],16)},{int(a[0:2],16)/255})"
            return '#'+a
        if t=='RectangleItem':
            bs=it['BorderStyle']; r=bs.get('RadiusTopLeft',0)
            b=f"border:1px solid {c(bs['BorderColor'])};" if bs.get('BorderTop') else ''
            bgc='#FFE63C28' if it['Name']=='ClassChipBg' else it['BackgroundColor']
            o.append(f'<div style="{st}background:{c(bgc)};border-radius:{r}px;{b}"></div>')
        elif t=='ImageItem':
            o.append(f'<img src="{imgs[it["Image"]]}" style="{st}">')
        elif t=='TextItem':
            al={0:'left',1:'center',2:'right'}[it['HorizontalAlignment']]
            txt=sample(it['Name'],it['Text'])
            o.append(f'<div style="{st}display:flex;align-items:center;justify-content:{ {"left":"flex-start","center":"center","right":"flex-end"}[al] };color:{c(it["TextColor"])};font-size:{it["FontSize"]}px;font-weight:700;line-height:1;white-space:nowrap">{txt}</div>')
        elif t=='LinearGaugeItem':
            mn,mx=it['Minimum'],it['Maximum']; val={'RPM':62,'Tyre':94,'Energy':61,'Fuel':71,'W_':94,'Delta':0}
            v=62 if it['Name'].startswith('RPM') else (0.21 if it['Name']=='DeltaFast' else (0 if it['Name']=='DeltaSlow' else 70))
            f=max(0,min(1,(v-mn)/(mx-mn)))
            al=it['GaugeAlignment']
            side='left:0' if al==0 else 'right:0'
            o.append(f'<div style="{st}background:{c(it["BackgroundColor"])};border-radius:{it["BorderStyle"].get("RadiusTopLeft",0)}px;overflow:hidden"><div style="position:absolute;{side};top:0;bottom:0;width:{f*100}%;background:{c(it["GaugeColor"])}"></div></div>')

        elif t=='DialGaugeItem':
            import math
            w,h=it['Width'],it['Height']; cx,cy=w/2,h/2; R=it['OuterRadius']; sa=it['StartAngle']; sw=it['SweepAngle']
            mx=8.0; red=7.0; val=6.2
            def P(a,r): a=math.radians(a); return cx+r*math.cos(a), cy+r*math.sin(a)
            g=[f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#99C8D2E0" stroke-width="{it["OuterStrokeThickness"]}"/>']
            mt=float(it['MajorTickSize'].split(',')[0]); mn=float(it['MinorTickSize'].split(',')[0])
            step=it['MajorDivisionsCount']; mdc=int(it['MinorDivisionsCount']); n=int(round(mx/step))
            for k in range(n+1):
                v=k*step; a=sa+sw*v/mx; col='#FF3B3B' if v>red else '#F2F2F6'
                x1,y1=P(a,it['MajorTickRadius']-mt/2); x2,y2=P(a,it['MajorTickRadius']+mt/2)
                g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="3"/>')
                if k<n:
                    for j in range(1,mdc+1):
                        vv=v+step*j/(mdc+1) if mdc else v
                        a2=sa+sw*vv/mx; x1,y1=P(a2,it['MinorTickRadius']-mn/2); x2,y2=P(a2,it['MinorTickRadius']+mn/2)
                        g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{"#FF3B3B" if vv>red else "#999"}" stroke-width="1"/>')
                if k%int(it['TicksPerLabel'])==0:
                    lx,ly=P(a,it['ScaleLabelStyle']['LabelRadius']); col='#FF3B3B' if v>red else '#F2F2F6'
                    g.append(f'<text x="{lx}" y="{ly}" fill="{col}" font-size="{it["ScaleLabelStyle"]["LabelFontSize"]}" font-weight="700" font-style="italic" font-family="Sui Generis" text-anchor="middle" dominant-baseline="central">{int(v)}</text>')
            o.append(f'<svg style="{st}" viewBox="0 0 {w} {h}">'+''.join(g)+'</svg>')
        elif t=='CircularGaugeItem':
            import math
            w,h=it['Width'],it['Height']; cx,cy=w/2,h/2; th=it['StrokeThickness']; r=w/2-th/2
            a0=it['MinAngle']-90; a1=it['MaxAngle']-90; f=0.78; af=a0+(a1-a0)*f
            def P(a): a=math.radians(a); return cx+r*math.cos(a), cy+r*math.sin(a)
            def arc(a,b,col):
                x1,y1=P(a); x2,y2=P(b); large=1 if (b-a)>180 else 0
                return f'<path d="M{x1},{y1} A{r},{r} 0 {large} 1 {x2},{y2}" fill="none" stroke="{col}" stroke-width="{th}"/>'
            o.append(f'<svg style="{st}" viewBox="0 0 {w} {h}">'+arc(a0,a1,"rgba(255,255,255,.15)")+arc(a0,af,"#FFE45C")+'</svg>')
    o.append('</div></body></html>'); return ''.join(o)
async def main():
    import zipfile,io
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':800,'height':480})
        for f in glob.glob('out_vidro/*.simhubdash'):
            z=zipfile.ZipFile(f); base=[n for n in z.namelist() if n.endswith('.djson')][0]
            d=json.loads(z.read(base)); res=zipfile.ZipFile(io.BytesIO(z.read(base+'.ressources')))
            imgs={n[:-4]:'data:image/png;base64,'+base64.b64encode(res.read(n)).decode() for n in res.namelist()}
            tag='ir' if 'iRacing' in f else 'lmu'
            for i,s in enumerate(d['Screens']):
                await pg.set_content(html(s,imgs)); await pg.screenshot(path=f'prevs_vidro_{tag}_{i}.png'); os.makedirs('thumbs_vidro',exist_ok=True); await pg.screenshot(path=f'thumbs_vidro/{tag}_{i}.png')
        await b.close()
asyncio.run(main())
