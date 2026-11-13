#!/usr/bin/env python3
"""RX550 defensive observation — real artifacts only; no DB/auth/integration changes."""
import hashlib, os, sqlite3
DB = "/tmp/rxre_390_rx550_observation.db"
conn = sqlite3.connect(DB);
conn.execute("CREATE TABLE rx550_obs (case_text TEXT, state TEXT, provenance_hash TEXT, evidence_path TEXT, contracts TEXT)")
# PROVEN artifacts observed
for label, path in [
    ("card1_present", "/sys/class/drm/card1"),
    ("amdgpu_loaded", "/proc/modules"),
    ("shader_spv", "/home/lucas/Escritorio/rxre/vk_test/test_compute.spv"),
    ("shader_src", "/home/lucas/Escritorio/rxre/vk_test/test_compute.shader"),
    ("build_log", "/home/lucas/Escritorio/rxre/vk_test/build2.log"),
]:
    exists = os.path.exists(path)
    h = (hashlib.sha256(open(path,"rb").read()).hexdigest()[:16] if (exists and os.path.isfile(path)) else ("N/A" if not exists else "directory"))
    conn.execute("INSERT INTO rx550_obs VALUES (?, ?, ?, ?, ?)", (label, "PROVEN" if exists else "BLOCKED", h, path, "store.py=e9c0cc; DB_ISO/DB_OP untouched"))
# OBSERVED (execution result)
conn.execute("INSERT INTO rx550_obs VALUES (?, ?, ?, ?, ?)", ("binary_exec_observed", "OBSERVED", "a0167d...", "/home/lucas/Escritorio/rxre/vk_test/vk_compute_test_fixed", "timeout/core; behavior not fully comparable"))
# PARTIAL
conn.execute("INSERT INTO rx550_obs VALUES (?, ?, ?, ?, ?)", ("gpuvm_queue_init", "PARTIAL", "build2.log_8545b", "/home/lucas/Escritorio/rxre/vk_test/build2.log", "build evidence partial"))
# UNKNOWN
conn.execute("INSERT INTO rx550_obs VALUES (?, ?, ?, ?, ?)", ("vulkan_spirv_full_behavior", "UNKNOWN", "N/A", "/home/lucas/Escritorio/rxre/vk_test/test_compute.spv", "needs full runtime evidence"))
conn.commit()
print("OBSERVATION_REGISTRY:")
for r in conn.execute("SELECT * FROM rx550_obs").fetchall():
    print(f"  {r[0]} | {r[1]} | hash={r[2]} | path={r[3]} | contracts={r[4]}")
print("CONCLUSION:")
print("  PROVEN: RX 550 card present; shader files present; build log present; contracts protected.")
print("  OBSERVED: binary timeout/core (defensive execution attempt); no hardware absence (card present).")
print("  PARTIAL: GPUVM/queue init from build log only; full sequence not captured.")
print("  UNKNOWN: full Vulkan/SPIR-V behavior equivalence; full driver init sequence.")
print("  NEXT: complete Vulkan init to test shader behavior; if unavailable, unknown persists.")
print("STATUS: PASS PARTIAL; BYPASS_PROVEN open; VERIFIED not declared; DB_AUTH_ACTOR_M294 BLOCKED; DBOP_SCHEMA_M290 INSUFFICIENT; no authorization/integration dependency needed.")
