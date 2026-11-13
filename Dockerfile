# Convenience environment for verification — OPTIONAL.
# The engine has NO hard dependency on Docker; verify.sh runs with plain
# gcc + sha256sum + python3 + pytest. This image exists for reviewers
# who prefer a pinned toolbox.
# NOTE: built and tested locally? NO — Docker was unavailable at authoring time;
# treat as convenience, not as a verified artifact.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "pytest>=8,<10"
WORKDIR /rxre-engine
COPY . .
CMD ["sh", "evidence/r3/verify.sh"]
