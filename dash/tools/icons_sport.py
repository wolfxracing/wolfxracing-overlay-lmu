import asyncio
from playwright.async_api import async_playwright
A='assets_sport'
ic={
 'farol':('<path d="M3 12a6 7 0 0 1 6-7c3.2 0 6 3 6 7s-2.800 7-6 7a6 7 0 0 1-6-7z"/><path d="M18 7h3.500M18 12h3.500M18 17h3.500"/>','#4DA3FF'),
 'motor':('<path d="M2.500 11v3M5 8.500h3l1.500-2h6v2.500h2.500l2 2v5.500l-2 2H9l-2.500-2.500H5z"/><path d="M11 6.500V4.500"/>','#FFB020'),
 'temp':('<path d="M9.500 14.500V5a2.500 2.500 0 0 1 5 0v9.500a4.500 4.500 0 1 1-5 0z"/><path d="M17.500 7.500h3M17.500 11.500h3"/>','#FF4A4A'),
 'pit':('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 16.500V7.500h3.500a2.800 2.800 0 0 1 0 5.600H9"/>','#FFB020'),
 'abs':('<circle cx="12" cy="12" r="9"/><text x="12" y="15.200" font-size="7.500" font-weight="700" text-anchor="middle" fill="currentColor" stroke="none" font-family="DejaVu Sans, Arial">ABS</text>','#FFB020'),
 'tc':('<path d="M5 17c0-5 3-9 7-9s7 4 7 9"/><path d="M8 20c1-2 2-3 4-3s3 1 4 3"/><circle cx="12" cy="5" r="1.100"/>','#FFB020'),
}
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':64,'height':64})
        for n,(svg,col) in ic.items():
            for st,c in (('off','rgba(255,255,255,0.26)'),('on',col)):
                html=f'<html><body style="margin:0;background:transparent"><svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="{c}" color="{c}" stroke-width="1.900" stroke-linecap="round" stroke-linejoin="round">{svg}</svg></body></html>'
                await pg.set_content(html); await pg.screenshot(path=f'{A}/MD4_i_{n}_{st}.png',omit_background=True)
        await b.close()
asyncio.run(main())
