import numpy as np
from PIL import Image, ImageDraw, ImageFilter
H,W=480,800; CX,CY=400,276
rng=np.random.default_rng(7)

def blob(canvas, cx, cy, r, col, amp):
    yy,xx=np.mgrid[0:H,0:W].astype(float)
    g=np.exp(-(((xx-cx)**2+(yy-cy)**2)/(2*r*r)))*amp
    canvas+=g[...,None]*np.array(col,float)

def base():
    t=(np.mgrid[0:H,0:W][0]/(H-1.0))[...,None]
    top=np.array([0x1B,0x20,0x2A],float); bot=np.array([0x0A,0x0C,0x11],float)
    b=top*(1-t)+bot*t
    # luzes suaves por tras do vidro (azul gelo, verde-agua, toque quente)
    blob(b, 120, 70, 150, (40,110,170), 0.55)
    blob(b, 690, 90, 170, (30,140,150), 0.40)
    blob(b, 640, 430, 190, (120,60,110), 0.34)
    blob(b, 90, 420, 170, (30,70,140), 0.38)
    # faixa de luz diagonal (reflexo no vidro)
    yy,xx=np.mgrid[0:H,0:W].astype(float)
    d=xx*0.6+yy*0.8
    b+=(np.exp(-((d-470.0)/60.0)**2)*10.0+np.exp(-((d-250.0)/38.0)**2)*6.0)[...,None]
    # granulado fino (acabamento fosco)
    b+=rng.normal(0,1.6,(H,W,1))
    return b

def finish(b, name_out, disc=False):
    yy,xx=np.mgrid[0:H,0:W].astype(float)
    v=np.clip(1-((xx-400)/560.0)**2-((yy-240)/350.0)**2,0.45,1)[...,None]
    img=Image.fromarray(np.clip(b*v,0,255).astype('uint8')).convert('RGBA')
    if disc:
        S=3
        layer=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); dr=ImageDraw.Draw(layer)
        def circ(r,fill=None,outline=None,w=1):
            dr.ellipse([(CX-r)*S,(CY-r)*S,(CX+r)*S,(CY+r)*S],fill=fill,outline=outline,width=int(w*S))
        # disco de vidro fume: miolo escuro, borda interna mais clara
        for r in range(196,0,-2):
            k=r/196.0
            circ(r,fill=(8,10,14,int(150+70*(1-k)**1.4)))
        # reflexo superior (meia-lua clara)
        hl=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); hd=ImageDraw.Draw(hl)
        hd.ellipse([(CX-176)*S,(CY-190)*S,(CX+176)*S,(CY+10)*S],fill=(255,255,255,26))
        m=Image.new('L',(W*S,H*S),0); md=ImageDraw.Draw(m)
        md.ellipse([(CX-190)*S,(CY-190)*S,(CX+190)*S,(CY+190)*S],fill=255)
        hl.putalpha(Image.fromarray((np.array(hl.split()[3],float)*np.array(m,float)/255.0*0.9).astype('uint8')))
        hl=hl.filter(ImageFilter.GaussianBlur(10*S))
        layer=Image.alpha_composite(layer,hl)
        dr=ImageDraw.Draw(layer)
        circ(196,outline=(255,255,255,90),w=2)
        circ(188,outline=(0,0,0,110),w=2)
        circ(150,outline=(255,255,255,26),w=1)
        layer=layer.resize((W,H),Image.LANCZOS)
        img=Image.alpha_composite(img,layer)
    img.convert('RGB').save(name_out)

finish(base(),'assets_vidro/MD4_bg.png',disc=True)
b2=base()
finish(b2,'assets_vidro/MD4_bg2.png',disc=False)
print('ok')
