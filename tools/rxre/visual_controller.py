#!/usr/bin/env python3
"""M371 — control visual minimo para Wanderburg (template matching con scipy)."""
import sys, os, json, hashlib, time, subprocess, tempfile
import numpy as np
from PIL import Image

TEMPLATE_DIR="/tmp/wanderburg_templates"
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def capture(outpath):
    subprocess.run(['ffmpeg','-f','x11grab','-video_size','1366x768','-i',':0.0','-frames:v','1','-y',outpath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return outpath

def to_gray(path):
    img=Image.open(path).convert('L')
    return np.array(img)

def match_template(screen_path, tmpl_path):
    s=to_gray(screen_path); t=to_gray(tmpl_path)
    if t.shape[0]>s.shape[0] or t.shape[1]>s.shape[1]:
        return 0.0
    from scipy.signal import correlate2d
    # use normalized cross-correlation via simple approach: mean subtracted
    s2=s.astype(float); t2=t.astype(float)
    s2=s2-s2.mean(); t2=t2-t2.mean()
    corr=correlate2d(s2, t2, mode='valid')
    # peak normalized
    peak=corr.max()
    denom=np.sqrt((s2*s2).sum()*(t2*t2).sum())+1e-9
    return float(peak/denom)

def recognize(screen_path, templates):
    best=None; bestscore=0.0
    for name,tpath in templates.items():
        if not os.path.exists(tpath): continue
        sc=match_template(screen_path,tpath)
        if sc>bestscore:
            bestscore=sc; best=name
    return best, bestscore

def save_template(name, screen_path, crop=None):
    img=Image.open(screen_path)
    if crop:
        img=img.crop(crop)
    out=os.path.join(TEMPLATE_DIR, name+'.png')
    img.save(out)
    return out

if __name__=='__main__':
    # demo: capture screen and list templates
    sp='/tmp/vc_screen.png'
    capture(sp)
    print('captured', sp)
    # list templates
    tpls={}
    for f in os.listdir(TEMPLATE_DIR):
        if f.endswith('.png'):
            tpls[f[:-4]]=os.path.join(TEMPLATE_DIR,f)
    if tpls:
        st,sc=recognize(sp,tpls)
        print('recognized:',st,'score:',sc)
    else:
        print('no templates; use save_template to create')
