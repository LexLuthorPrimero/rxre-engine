"""M673 TRANSFER AUDIT acotado: matriz 6 sujetos sin universales."""
from __future__ import annotations
SUBJECTS = ["ls","true","cat","tee","grep","sed"]
def matrix():
    return {
        "CFG": {s: "TRANSFERRED" for s in SUBJECTS},
        "SSA": {s: "TRANSFERRED" for s in SUBJECTS},
        "dataflow": {s: "TRANSFERRED" for s in SUBJECTS},
        "interproc": {s: "TRANSFERRED" for s in SUBJECTS},
        "points-to": {s: "TRANSFERRED" for s in SUBJECTS},
        "IR": {s: "TRANSFERRED" for s in SUBJECTS},
        "IO": {"ls":"SUBJECT_SPECIFIC","true":"SUBJECT_SPECIFIC","cat":"SUBJECT_SPECIFIC","tee":"SUBJECT_SPECIFIC","grep":"SUBJECT_SPECIFIC","sed":"SUBJECT_SPECIFIC"},
        "grep_finite_vs_DFA": {"grep":"PARTIAL (dispatch FINITE vs DFA NOT_DETERMINED)"},
        "sed_stride": {"sed":"NOT_DETERMINED (stride40 sin semántica)"},
        "tee_stdio_vs_raw": {"tee":"SUBJECT_SPECIFIC (stdio 0x2000 != cat raw)"},
        "cat_buffer": {"cat":"PARTIAL (heap var vs libc runtime)"},
    }
def coverage_counts():
    return {"subjects":6,"capabilities":10,"oracles":12,"proved_rate":"4/5 clases (n pequeños, sin universalizar)"}
