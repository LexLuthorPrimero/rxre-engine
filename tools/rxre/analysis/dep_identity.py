"""M639 DEP IDENTITY: inventario ELF deps sin ejecutar sujeto. Identidad exacta vs compatible."""
from __future__ import annotations
import subprocess, hashlib

def inventory(binpath="/usr/bin/ls"):
    out=subprocess.run(["readelf","-d",binpath],capture_output=True,text=True,timeout=15).stdout
    needed=[]
    for line in out.splitlines():
        if "NEEDED" in line:
            needed.append(line.split("[")[-1].strip("]"))
    interp=subprocess.run(["readelf","-l",binpath],capture_output=True,text=True,timeout=15).stdout
    interp_path="/lib64/ld-linux-x86-64.so.2" if "ld-linux" in interp else "?"
    build=subprocess.run(["readelf","-n",binpath],capture_output=True,text=True,timeout=15).stdout
    import re
    m=re.search(r"ID de Compilaci.n: (\w+)", build)
    build_id=m.group(1) if m else "?"
    return {"bin":binpath,"interp":interp_path,"needed":needed,"build_id":build_id,
            "rpath":"ausente","runpath":"ausente"}

def lib_identity(path):
    h=hashlib.sha256(open(path,"rb").read()).hexdigest()
    fileout=subprocess.run(["file",path],capture_output=True,text=True,timeout=10).stdout
    import re
    m=re.search(r"BuildID\[sha1\]=(\w+)", fileout)
    build=m.group(1) if m else "?"
    compat="ELF 64-bit LSB" in fileout and "x86-64" in fileout
    return {"path":path,"sha":h,"build_id":build,"compat":compat}

def summarize_external(symbol, body_events, identity_ok):
    """body_events None => unknown; si existe pero efectos no modelados => unknown (conservador)."""
    if body_events is None or not identity_ok:
        return {"name":symbol,"unknown":True,"why":"sin cuerpo local verificado o identidad incompleta"}
    return {"name":symbol,"unknown":True,"why":"cuerpo existe pero efectos runtime no modelados (conservador)"}
