"""M666 COVERAGE AUDIT recheck: correspondencia M664-M665 + inventario adicional.
Solo lectura (grep). Sin invocar ejecución."""
from __future__ import annotations

AUDITED = ["0x18e0","0xcf1d","0x1288a","0x12fe6","0x13ca9","0x13ee9","0x16f33","0x180d8","0x18135","0x1a1ed","0x1c20b","0x1c366","0x1ca93","0x1cdf3"]
ADDITIONAL = ["0x34cf","0x3510"]

def correspondence(m664_sites, m665_sites):
    return {"audited": len([s for s in m664_sites if s in m665_sites]),
            "dup": len(m664_sites)-len(set(m664_sites)),
            "missing": [s for s in m664_sites if s not in m665_sites]}

def coverage():
    return {"funcs":259,"blocks":5504,"edges":8058,
            "audited":14,"additional_may":len(ADDITIONAL),
            "uncovered":ADDITIONAL}
