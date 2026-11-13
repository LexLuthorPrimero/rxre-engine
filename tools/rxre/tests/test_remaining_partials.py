
"""Cierre de 14 PARTIAL restantes."""
import pytest, threading, queue

def test_alma_a1():
    from tools.rxre.arquitectura import ALMA
    claim = {"scope":"x","evidence_refs":[{"hash":"h","provenance":"p"}],
             "contradiction_refs":[],"falsification_test":"f",
             "unresolved_obligations":[],"epistemic_state":"PROVEN"}
    c = ALMA.criterio_cierre(claim)
    assert len(c)==7 and all(isinstance(v,bool) for v in c.values())

def test_alma_a2():
    from tools.rxre.arquitectura import ALMA
    assert ALMA.proposito_declarado() == ALMA.PROPOSITO

def test_alma_a3():
    from tools.rxre.arquitectura import ALMA
    assert ALMA.media_sync_obligatoria() is False

def test_aire_ai1():
    from tools.rxre.arquitectura import AIRE
    tid = AIRE.emitir_traza(decision="test",herramienta={"name":"x","version":"1"},resultado={"y":1})
    t = AIRE.reconstruir_traza(tid)
    assert "decision" in t and "herramienta" in t and "resultado" in t

def test_aire_ai3():
    from tools.rxre.arquitectura import AIRE
    h = AIRE.tool_hash({"name":"x","version":"1"})
    assert len(h)==64 and h == AIRE.tool_hash({"name":"x","version":"1"})

def test_mente_m1():
    from tools.rxre.arquitectura.planos import Mente
    m = Mente()
    assert len(m.hipotesis_rivales(["a","b"])) == 2
    with pytest.raises(ValueError): m.hipotesis_rivales(["solo"])

def test_mente_m2():
    from tools.rxre.arquitectura.planos import Mente
    m = Mente()
    r = m.causalidad("a","b","prueba")
    assert r["discriminada"] is True
    with pytest.raises(ValueError): m.causalidad("a","b","")

def test_mente_m3():
    from tools.rxre.arquitectura.planos import Mente
    m = Mente()
    m.set_cfg({"nodes":["n1"],"edges":[]})
    assert m.get_cfg()=={"nodes":["n1"],"edges":[]}

def test_mente_m5_m6_canales_fifo_1_1():
    from tools.rxre.arquitectura.planos import Mente
    m = Mente()
    m.enviar_a_cuerpo({"x":1})
    t = threading.Thread(target=m.enviar_a_cuerpo, args=({"x":2},), daemon=True)
    t.start(); t.join(timeout=0.3)
    assert t.is_alive(), "segundo put debe bloquear"
    m.out_to_cuerpo.get()
    m.enviar_a_fuego({"y":1})
    t2 = threading.Thread(target=m.enviar_a_fuego, args=({"y":2},), daemon=True)
    t2.start(); t2.join(timeout=0.3)
    assert t2.is_alive()
    m.out_to_fuego.get()

def test_cuerpo_c1():
    from tools.rxre.arquitectura.planos import Cuerpo
    c = Cuerpo()
    assert c.observar({"v":1}, simulado=False)["_real"] is True
    assert c.observar({"v":1}, simulado=True)["_real"] is False

def test_cuerpo_c2():
    from tools.rxre.arquitectura.planos import Cuerpo
    c = Cuerpo()
    r = c.medir(1.0,"V",{"temp":25})
    assert r["unidad"]=="V" and r["condiciones"]["temp"]==25
    with pytest.raises(ValueError): c.medir(1.0,"",{})

def test_cuerpo_c3():
    from tools.rxre.arquitectura.planos import Cuerpo
    c = Cuerpo()
    art = c.artefacto(b"datos")
    assert len(art["hash"])==64
    assert c.leer_artefacto_verificado(art)==b"datos"

def test_cuerpo_c4():
    from tools.rxre.arquitectura.planos import Cuerpo
    c = Cuerpo()
    art = c.artefacto(b"datos")
    art["contenido"]=b"alterado"
    with pytest.raises(ValueError): c.leer_artefacto_verificado(art)

def test_cuerpo_c5_c6_canales():
    from tools.rxre.arquitectura.planos import Cuerpo
    c = Cuerpo()
    c.enviar_a_mente({"x":1})
    t = threading.Thread(target=c.enviar_a_mente, args=({"x":2},), daemon=True)
    t.start(); t.join(timeout=0.3); assert t.is_alive()
    c.out_to_mente.get()
    c.enviar_a_fuego({"y":1})
    t2 = threading.Thread(target=c.enviar_a_fuego, args=({"y":2},), daemon=True)
    t2.start(); t2.join(timeout=0.3); assert t2.is_alive()
    c.out_to_fuego.get()

def test_fuego_f1():
    from tools.rxre.arquitectura.planos import Fuego
    f = Fuego()
    r = f.transformar(1, lambda x: x+1, {"scope":"local"})
    assert r["ok"] is True and r["resultado"]==2
    with pytest.raises(ValueError): f.transformar(1, lambda x: x, {})

def test_fuego_f3_f4_canales():
    from tools.rxre.arquitectura.planos import Fuego
    f = Fuego()
    f.enviar_a_mente({"x":1})
    t = threading.Thread(target=f.enviar_a_mente, args=({"x":2},), daemon=True)
    t.start(); t.join(timeout=0.3); assert t.is_alive()
    f.out_to_mente.get()
    f.enviar_a_cuerpo({"y":1})
    t2 = threading.Thread(target=f.enviar_a_cuerpo, args=({"y":2},), daemon=True)
    t2.start(); t2.join(timeout=0.3); assert t2.is_alive()
    f.out_to_cuerpo.get()

def test_agua_g1():
    from tools.rxre.arquitectura import AGUA
    AGUA.aprender("L1",{"x":1},{"source":"exp_A"})
    r = AGUA.recuperar("L1")
    assert r["procedencia"]["source"]=="exp_A"
    with pytest.raises(ValueError): AGUA.aprender("L2",{"x":2},{})

def test_agua_g3():
    from tools.rxre.arquitectura import AGUA
    with pytest.raises(ValueError): AGUA.invocar_capacidad("sin_formato", {})

def test_router_r2():
    from tools.rxre.core.dispatch import verificar_capacidades_minimas
    full = {"binary.functions":"rz","binary.disassemble":"cs","binary.xrefs":"rz","source.semantic_search":"cc"}
    assert verificar_capacidades_minimas(full)["completas"] is True
    assert len(verificar_capacidades_minimas({"binary.functions":"x"})["faltantes"])==3
