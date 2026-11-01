import numpy as np, math
from PIL import Image, ImageDraw, ImageFilter
H,W=480,800; CX,CY=400,276

def carbon(amp=11.0, cell=4):
    yy,xx=np.mgrid[0:H,0:W]
    bx=xx//cell; by=yy//cell
    lx=(xx%cell)/(cell-1.0); ly=(yy%cell)/(cell-1.0)
    horiz=(((bx//2)+(by//2))%2==0)
    # trama "twill" 2x2: faixas horizontais e verticais alternadas, cada uma com brilho (claro->escuro)
    sh=np.where(horiz,1-ly,1-lx)
    sh=np.where(((bx+by)%2==0),sh,0.5*sh+0.25)            # variacao entre fibras vizinhas
    return (sh-0.5)*2*amp

def base(strong=True):
    t=(np.mgrid[0:H,0:W][0]/(H-1.0))[...,None]
    top=np.array([0x22,0x23,0x2A]); bot=np.array([0x0A,0x0B,0x0E])
    b=top*(1-t)+bot*t
    b=b+carbon(17.0 if strong else 13.0)[...,None]
    # reflexo diagonal suave (brilho de verniz)
    yy,xx=np.mgrid[0:H,0:W].astype(float)
    d=(xx*0.55+yy*0.83)
    band=np.exp(-((d-430.0)/70.0)**2)*14.0+np.exp(-((d-700.0)/55.0)**2)*8.0
    b=b+band[...,None]
    return b

def finish(b, glow, name_out, disc=False):
    yy,xx=np.mgrid[0:H,0:W].astype(float)
    d=np.sqrt((xx-CX)**2+(yy-CY)**2)
    g=np.clip(1-d/310.0,0,1)**2.2
    b=b+g[...,None]*np.array(glow)
    v=np.clip(1-((xx-CX)/540.0)**2-((yy-CY)/340.0)**2,0.40,1)[...,None]
    b=b*v
    img=Image.fromarray(np.clip(b,0,255).astype('uint8')).convert('RGBA')
    if disc:
        S=3
        layer=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); dr=ImageDraw.Draw(layer)
        def circ(r,fill=None,outline=None,w=1):
            dr.ellipse([(CX-r)*S,(CY-r)*S,(CX+r)*S,(CY+r)*S],fill=fill,outline=outline,width=int(w*S))
        for r in range(196,0,-2):
            k=r/196.0; c=int(9+15*(1-k)**1.6)
            circ(r,fill=(c,c,c+2,250))
        # hexagonos (favo) recortados no disco
        hexl=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); hd=ImageDraw.Draw(hexl)
        R=24.0; hw=R*math.sqrt(3)
        for row in range(-2,22):
            for col in range(-2,28):
                cx=col*hw+(hw/2 if row%2 else 0); cy=row*R*1.5
                pts=[(cx+R*math.cos(math.radians(60*k+30)), cy+R*math.sin(math.radians(60*k+30))) for k in range(6)]
                pts=[((x)*S,(y)*S) for x,y in pts]
                hd.line(pts+[pts[0]],fill=(255,255,255,26),width=int(1.2*S))
        mask=Image.new('L',(W*S,H*S),0); md=ImageDraw.Draw(mask)
        md.ellipse([(CX-150)*S,(CY-150)*S,(CX+150)*S,(CY+150)*S],fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(14*S))
        hexl.putalpha(Image.eval(mask,lambda v:v).point(lambda v:v) if False else Image.fromarray((np.array(hexl.split()[3],float)*np.array(mask,float)/255.0).astype('uint8')))
        layer=Image.alpha_composite(layer,hexl)
        dr=ImageDraw.Draw(layer)
        circ(196,outline=(64,66,76,255),w=2)
        circ(150,outline=(255,255,255,16),w=1)
        dr.rectangle([(CX-26)*S,(CY-198)*S,(CX+26)*S,(CY-195)*S],fill=(224,49,63,255))
        layer=layer.resize((W,H),Image.LANCZOS)
        img=Image.alpha_composite(img,layer)
    img.convert('RGB').save(name_out)

finish(base(True),[70,8,12],'assets_sport/MD4_bg.png',disc=True)
finish(base(False),[22,3,5],'assets_sport/MD4_bg2.png',disc=False)
