# Convenience environment for verification — OPTIONAL.
# The engine needs only gcc + sha256sum + python3 + pytest; verify.sh runs fine
# outside containers too. Base image pinned to Fedora 44 because the sealed
# evidence records hash 54e936d3… of /usr/bin/ls (Fedora 44 coreutils 9.10-5).
# Semantic note: if Fedora's coreutils build changes, /bin/ls will no longer match
# the sealed hash and the integrity-bound suites will report a mismatch.
FROM fedora:44
RUN dnf install -y --setopt=install_weak_deps=False python3-pytest gcc python3 && dnf clean all
WORKDIR /rxre-engine
COPY . .
CMD ["sh", "evidence/r3/verify.sh"]
