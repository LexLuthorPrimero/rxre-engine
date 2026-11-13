"""MUNDO REAL — backends de investigación reales."""
import ast, hashlib, subprocess, os

def w1_investigar_codigo_fuente(path):
    if not os.path.exists(path): raise FileNotFoundError(path)
    with open(path, "r") as f: src = f.read()
    tree = ast.parse(src)
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    return {"path": path, "funciones": funcs, "hash": hashlib.sha256(src.encode()).hexdigest(), "real": True}

def w2_investigar_binario(path):
    if not os.path.exists(path): raise FileNotFoundError(path)
    try:
        out = subprocess.check_output(["readelf", "-h", path], stderr=subprocess.DEVNULL, timeout=5)
        tipo = [l for l in out.decode().splitlines() if "Type:" in l]
        return {"path": path, "readelf_ok": True, "tipo": tipo[0] if tipo else "?", "real": True}
    except (subprocess.CalledProcessError, FileNotFoundError):
        with open(path, "rb") as f: magic = f.read(4)
        return {"path": path, "elf_magic": magic.hex(), "real": True}

def w6_pcie_lectura(device="0000:01:00.0"):
    base = f"/sys/bus/pci/devices/{device}"
    if not os.path.exists(base): raise FileNotFoundError(base)
    def rd(f):
        with open(os.path.join(base, f)) as fh: return fh.read().strip()
    return {"device": device, "vendor": rd("vendor"), "device_id": rd("device"), "class": rd("class"), "real": True}
