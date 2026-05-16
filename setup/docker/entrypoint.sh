#!/usr/bin/env bash
set -euo pipefail

shutdown() {
  echo "Stopping Hermes container..."
  if [[ -n "${child_pid:-}" ]] && kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 0
}
trap shutdown SIGTERM SIGINT

# Persist default Hermes provider/model into Hermes config without using
# HERMES_INFERENCE_* runtime overrides.
if [[ -n "${HERMES_DEFAULT_PROVIDER:-}" || -n "${HERMES_DEFAULT_MODEL:-}" ]]; then
  python3 - <<'PY'
import os
from pathlib import Path
p = Path(os.environ.get("HERMES_HOME", "/root/.hermes")) / "config.yaml"
if p.exists():
    text = p.read_text()
    model = os.environ.get("HERMES_DEFAULT_MODEL", "").strip()
    provider = os.environ.get("HERMES_DEFAULT_PROVIDER", "").strip()
    if model:
        import re
        text = re.sub(r'(?m)^(\s*default:\s*).+$', rf'\1"{model}"', text, count=1)
    if provider:
        import re
        text = re.sub(r'(?m)^(\s*provider:\s*).+$', rf'\1"{provider}"', text, count=1)
    p.write_text(text)
PY
fi

# Initialize GBrain's local PGLite brain on first container start. This is
# idempotent; persistent data lives in the hermes-home volume under /root/.gbrain.
if command -v gbrain >/dev/null 2>&1 && [[ "${GBRAIN_INIT_ON_START:-true}" == "true" ]]; then
  # GBrain treats GBRAIN_HOME as a parent directory and stores data in
  # $GBRAIN_HOME/.gbrain. With the Docker volume mounted at /root, this persists.
  gbrain_parent="${GBRAIN_HOME:-/root}"
  gbrain_config_dir="${gbrain_parent%/}/.gbrain"
  if [[ ! -e "${gbrain_config_dir}/brain.pglite" ]]; then
    echo "Initializing GBrain..."
    gbrain init || true
  fi
  if [[ -n "${GBRAIN_SEARCH_MODE:-}" ]]; then
    gbrain config set search.mode "${GBRAIN_SEARCH_MODE}" || true
  fi
fi

if [[ -n "${HERMES_COMMAND:-}" ]]; then
  echo "Starting Hermes agent: ${HERMES_COMMAND}"
  bash -lc "${HERMES_COMMAND}" &
  child_pid=$!
  wait "$child_pid"
else
  echo "HERMES_COMMAND is not set. Container will stay alive."
  echo "Exec into it with: docker compose exec hermes bash"
  tail -f /dev/null &
  child_pid=$!
  wait "$child_pid"
fi
