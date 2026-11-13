"""M664 INDEX TRACE acotado: origen/transforms/dominio por salto indirecto (grep)."""
from __future__ import annotations

# Tabla por salto (evidencia objdump): (site, base, idx_transforms, guard, dest_form, status)
# Status: FINIT/MAY/NOT_DETERMINED con cota via guard demostrado
ROWS = [
    ("0x18e0","lea 0x223c8","eax: cmp 0x89/ja + movq→movslq x4","0..137 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0xcf1d","lea 0x22380","eax-0x3f: cmp 0x11/ja","0..17 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x1288a","lea 0x226e0","rbx: cmp 0x9/ja","0..9 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x12fe6","lea 0x22708","r10: cmp 0x12/ja","0..18 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x13ca9","lea 0x22754","rax: cmp 0x6/ja","0..6 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x13ee9","lea 0x22770","rcx: cmp 0x11/ja","0..17 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x16f33","lea 0x227b8","rax: cmp 0x13/ja + lea -0x100","0..19 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x180d8","lea 0x22808","bl: cmp 0x35/ja + sub 0x42","0..53 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x18135","lea 0x228e0","bl: cmp 0x35/ja + sub 0x42","0..53 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x1a1ed","lea 0x229b8","al: cmp 0x73/ja + sub 0xa","0..115 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x1c20b","lea 0x22b88","eax: cmp 0xa/ja","0..10 guard ja","dest=base+off","FINITE_TARGET_SET"),
    ("0x1c366","lea 0x22bb4","r12b: cmp 0x23/ja + jg/js","0..35 guard ja/jg/js","dest=base+off","FINITE_TARGET_SET"),
    ("0x1ca93","lea 0x22c44","r12b: cmp 0x23/ja + jg/js","0..35 guard ja/jg/js","dest=base+off","FINITE_TARGET_SET"),
    ("0x1cdf3","lea 0x22cd4","r12b: cmp 0x23/ja + jg/js","0..35 guard ja/jg/js","dest=base+off","FINITE_TARGET_SET"),
]

def table():
    return [{"site":s,"base":b,"transforms":t,"guard":g,"dest":d,"status":st} for s,b,t,g,d,st in ROWS]

def classify(st):
    return st  # never upgrades unknown

def proven_count():
    return sum(1 for _,_,_,_,_,st in ROWS if st=="FINITE_TARGET_SET")
