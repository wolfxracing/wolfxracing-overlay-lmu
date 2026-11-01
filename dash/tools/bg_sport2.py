import numpy as np
from PIL import Image, ImageDraw, ImageFilter
H,W=480,800; CX,CY=400,276
yy,xx=np.mgrid[0:H,0:W].astype(float)
# base: grafite quase preto, leve gradiente vertical
base=np.zeros((H,W,3))
t=(yy/(H-1))[...,None]
top=np.array([0x14,0x15,0x1A]); bot=np.array([0x07,0x08,0x0B])
base=top*(1-t)+bot*t
# fibra de carbono muito sutil
q=((xx//3)%2)+2*((yy//3)%2)
carb=np.where((q==0)|(q==3),-3.0,2.0)[...,None]
base+=carb
# brilho vermelho suave atras do mostrador
d=np.sqrt((xx-CX)**2+(yy-CY)**2)
glow=np.clip(1-d/300.0,0,1)**2.2
base+=glow[...,None]*np.array([22,3,5])
# vinheta
v=np.clip(1-((xx-CX)/520.0)**2-((yy-CY)/330.0)**2,0.35,1)[...,None]
base*=v
img=Image.fromarray(np.clip(base,0,255).astype('uint8')).convert('RGBA')
img.convert('RGB').save('assets_sport/MD4_bg2.png')
