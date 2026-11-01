import json,zipfile,subprocess,sys,glob,os,collections
bad=0
for f in glob.glob('out_sport/*.simhubdash'):
    z=zipfile.ZipFile(f); names=z.namelist(); print(f,names)
    base=[n for n in names if n.endswith('.djson')][0]
    d=json.loads(z.read(base).decode('utf-8'))
    EXT='\n'.join(z.read(n).decode('utf-8') for n in names if n.endswith('.js'))
    imgs={i['Name'] for i in d['Images']}
    res=zipfile.ZipFile(__import__('io').BytesIO(z.read(base+'.ressources'))).namelist()
    assert all(i+'.png' in res for i in imgs)
    sids={s['ScreenId'] for s in d['Screens']}
    js=[]
    for s in d['Screens']:
        nm=collections.Counter(i['Name'] for i in s['Items'])
        dup=[k for k,v in nm.items() if v>1]
        if dup: print('DUP names',s['Name'],dup); bad+=1
        for it in s['Items']:
            if it.get('Image') and it['Image'] not in imgs: print('missing img',it['Image']); bad+=1
            b=it.get('Behavior')
            if b and b['Settings']['ScreenId'] not in sids: print('bad target'); bad+=1
            for k,v in (it.get('Bindings') or {}).items():
                fm=v['Formula']
                if fm.get('Interpreter')==1: js.append((s['Name'],it['Name'],k,(EXT+'\n' if fm.get('JSExt') else '')+fm['Expression']))
            if not (0<=it['Left']<=800 and 0<=it['Top']<=480 and it['Left']+it['Width']<=800.01 and it['Top']+it['Height']<=480.01):
                print('OUT OF BOUNDS',s['Name'],it['Name'],it['Left'],it['Top'],it['Width'],it['Height']); bad+=1
    open('/tmp/jscheck.js','w').write('const $prop=()=>null; const root={};\n'+'\n'.join('try{ new Function("$prop","root",%s)($prop,root); }catch(e){console.log("JSERR",%s,e.message)}'%(json.dumps(e),json.dumps(f"{a}/{b}/{c}")) for a,b,c,e in js))
    r=subprocess.run(['node','/tmp/jscheck.js'],capture_output=True,text=True); print(len(js),'js exprs;',r.stdout.strip() or 'ok',r.stderr[:200]); bad+= 'JSERR' in r.stdout
print('PROBLEMS:',bad)
