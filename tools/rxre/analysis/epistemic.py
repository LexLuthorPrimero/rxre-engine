"""M657 EPISTEMIC CALIBRATION acotado: muestra trazable, criterios previos, métricas con denominadores."""
from __future__ import annotations

def select_sample(claims):
    # solo claims con evidencia+oráculo trazable y oracle != productor
    return [c for c in claims if c.get("evidence") and c.get("oracle") not in (None,"","NO-DISPONIBLE","ninguno") and c.get("oracle_component")!=c.get("producer")]

def classify_result(state, observation_status):
    # observation_status: "confirms" | "refutes" | "no_says"
    if observation_status=="confirms": return "CONFIRMED"
    if observation_status=="refutes": return "REFUTED"
    return "UNRESOLVED"

def metrics(samples_results):
    # samples_results: [(estado_histórico, resultado)]
    from collections import Counter
    c=Counter(samples_results)
    n=len(samples_results)
    if n==0: return {"denominator":0,"note":"INSUFFICIENT"}
    proven=[r for s,r in samples_results if s=="PROVEN"]
    notd=[r for s,r in samples_results if s=="NOT_DETERMINED"]
    return {"n":n,
            "proven_confirmed": f"{sum(1 for r in proven if r=='CONFIRMED')}/{len(proven)}" if proven else "0/0",
            "proven_refuted": f"{sum(1 for r in proven if r=='REFUTED')}/{len(proven)}" if proven else "0/0",
            "notd_unresolved": f"{sum(1 for r in notd if r=='UNRESOLVED')}/{len(notd)}" if notd else "0/0",
            "note":"solo clases comparables, sin universalizar"}
