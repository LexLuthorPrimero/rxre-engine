# Empirical Hardware-Bridge Transpiler — Fase 4 (v0.1.0)

Traduce semántica de subgrupo (ballot/shuffle/barrera) a SPIR-V GLSL adaptada a wavefront 32/64, con harness empírico `require_gpu()`/`vk_cf_test` sobre RX550/RADV (E2E-006-019, 120+ targets, 0 fallos). Respeta `AGENTS §5` (sin `/dev/mem`, `sysfs`, `debugfs`, `UMR`, root).

Estado `PASS_PARTIAL` acotado: traducción + asamblea verificadas; sin equivalencia formal, sin ports reales NVIDIA→AMD/RISC-V demostrados, `PROVEN` no promovido.
