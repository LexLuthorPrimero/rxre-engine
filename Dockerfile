# Convenience environment for verification — OPTIONAL.
# The engine needs only gcc + sha256sum + python3 + pytest; verify.sh runs fine
# outside containers too. Base image digest pinned (resolved 2026-11-13 on the author
# host via podman pull fedora:44; digest = manifest, not a claim of safety — the
# sealed-evidence hash check in verify.sh is the real gate). Package versions inside
# the image are NOT individually pinned; dnf installs at build time. If Fedora's
# coreutils build changes, /bin/ls will no longer match the sealed hash and the
# integrity-bound suites will report a mismatch (fail-closed), not a silent pass.
FROM docker.io/library/fedora@sha256:15da97ed9aa94dd3d92c3925eb89520f6c80e07ea7ee24cba848d1f8b6912b3e
RUN dnf install -y --setopt=install_weak_deps=False python3-pytest gcc python3 && dnf clean all
WORKDIR /rxre-engine
COPY . .
CMD ["sh", "evidence/r3/verify.sh"]
