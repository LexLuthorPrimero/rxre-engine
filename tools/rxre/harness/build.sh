#!/bin/sh
# Build RXRE harnesses + fixtures (persisted in-repo; survives /tmp purges).
set -e
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$HERE/bin"
gcc -O1 -o "$HERE/bin/vk_cf_test" "$HERE/vk_cf_test.c" -lvulkan
gcc -O1 -o "$HERE/bin/vk_headless_render" "$HERE/vk_headless_render.c" -lvulkan
gcc -O1 -o "$HERE/bin/gl_headless_render" "$HERE/gl_headless_render.c" -lEGL -lGL -lm
for f in "$HERE"/fixtures/*/kernels/*.comp; do
    glslangValidator -V -o "${f%.comp}.spv" "$f" > /dev/null
done
# Canonical shaders (POLARIS-028..030) — compile + compile-only ISA capture (zero GPU work)
python3 - "$HERE" <<'PYX'
import sys, os, subprocess
sys.path.insert(0, '/home/lucas/Escritorio/rxre/tools')
from rxre.polaris12 import gpu_control_flow
HERE = sys.argv[1]
outdir = os.path.join(HERE, 'fixtures', 'canonical')
os.makedirs(os.path.join(outdir, 'isa'), exist_ok=True)
for name, glsl in gpu_control_flow.SHADER_TEMPLATES.items():
    comp = os.path.join(outdir, name + '.comp')
    if not os.path.exists(comp):
        open(comp, 'w').write(glsl)
for comp in sorted(__import__('glob').glob(os.path.join(outdir, '*.comp'))):
    name = os.path.basename(comp)[:-5]
    spv = os.path.join(outdir, name + '.spv')
    cmd = ['glslangValidator', '-V', '-o', spv, comp]
    if name == 'laneops':
        cmd = ['glslangValidator', '--target-env', 'vulkan1.1', '-V', '-o', spv, comp]
    subprocess.run(cmd, check=True, capture_output=True)
    has_in = '1' if name == 'barrier_sync' else '0'
    with open(os.path.join(outdir, 'isa', name + '_isa_full.txt'), 'w') as fh:
        subprocess.run([os.path.join(HERE, 'bin', 'vk_cf_test'), spv, '64', has_in, '--no-run'],
                       stdout=fh, stderr=subprocess.STDOUT, env={'PATH': '/usr/bin:/bin', 'RADV_DEBUG': 'asm'}, check=False)
PYX
echo "BUILD_OK $HERE/bin"
