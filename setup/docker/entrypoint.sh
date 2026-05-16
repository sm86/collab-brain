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

seed_profile_file() {
  local src="$1"
  local dst="$2"

  if [[ ! -f "${src}" ]]; then
    echo "Hermes profile seed file missing: ${src}" >&2
    return 0
  fi
  if [[ -e "${dst}" || -L "${dst}" ]]; then
    return 0
  fi
  if [[ -d "${dst}" ]]; then
    echo "Hermes profile destination is a directory, skipping: ${dst}" >&2
    return 0
  fi

  mkdir -p "$(dirname "${dst}")"
  if ! cp -- "${src}" "${dst}"; then
    echo "Failed to seed Hermes profile file ${dst} from ${src}" >&2
  fi
}

# Seed the Hermes identity and memory profile from a tracked template on first
# start. This is non-destructive: existing user-edited files always win.
if [[ "${HERMES_BOOTSTRAP_PROFILE:-true}" == "true" ]]; then
  hermes_home="${HERMES_HOME:-/root/.hermes}"
  profile_dir="${HERMES_PROFILE_TEMPLATE_DIR:-/opt/hermes/mock-garry-profile}"
  if [[ -d "${profile_dir}" ]]; then
    seed_profile_file "${profile_dir}/SOUL.md" "${hermes_home}/SOUL.md"
    seed_profile_file "${profile_dir}/config.yaml" "${hermes_home}/config.yaml"
    seed_profile_file "${profile_dir}/USER.md" "${hermes_home}/memories/USER.md"
    seed_profile_file "${profile_dir}/MEMORY.md" "${hermes_home}/memories/MEMORY.md"
  else
    echo "Hermes profile template not found: ${profile_dir}" >&2
  fi
fi

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

    def upsert_scalar(src, key, value):
        import re
        pattern = rf'(?m)^(\s*{re.escape(key)}:\s*).+$'
        replacement = rf'\1"{value}"'
        updated, count = re.subn(pattern, replacement, src, count=1)
        if count:
            return updated
        prefix = f'{key}: "{value}"\n'
        return prefix + src

    if model:
        text = upsert_scalar(text, "default", model)
    if provider:
        text = upsert_scalar(text, "provider", provider)
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
  if [[ "${GBRAIN_IMPORT_MOCK_GARRY_ON_START:-true}" == "true" ]]; then
    garry_mock_source="${GBRAIN_MOCK_GARRY_SOURCE:-/opt/hermes/mockdata/garry}"
    garry_mock_marker="${gbrain_config_dir}/.mock-garry-imported"
    if [[ ! -e "${garry_mock_marker}" ]]; then
      if [[ -d "${garry_mock_source}" ]]; then
        echo "Importing Garry mock GBrain data..."
        if gbrain import "${garry_mock_source}" --no-embed; then
          touch "${garry_mock_marker}" || true
        else
          echo "Failed to import Garry mock GBrain data from ${garry_mock_source}" >&2
        fi
      else
        echo "Garry mock GBrain data not found: ${garry_mock_source}" >&2
      fi
    fi
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
