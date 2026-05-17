#!/usr/bin/env bash
set -euo pipefail

shutdown() {
  echo "Stopping Hermes container for ${PARTNER_NAME:-Hermes}..."
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

seed_profile_plugins() {
  local src_dir="$1"
  local dst_dir="$2"

  if [[ ! -d "${src_dir}" ]]; then
    return 0
  fi

  mkdir -p "${dst_dir}"
  local plugin_src plugin_name plugin_dst
  for plugin_src in "${src_dir}"/*; do
    [[ -d "${plugin_src}" ]] || continue
    plugin_name="$(basename "${plugin_src}")"
    plugin_dst="${dst_dir}/${plugin_name}"
    if [[ -e "${plugin_dst}" || -L "${plugin_dst}" ]]; then
      continue
    fi
    if cp -a -- "${plugin_src}" "${plugin_dst}"; then
      hermes plugins enable "${plugin_name}" >/dev/null 2>&1 || true
    else
      echo "Failed to seed Hermes plugin ${plugin_dst} from ${plugin_src}" >&2
    fi
  done
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
    seed_profile_plugins "${profile_dir}/plugins" "${hermes_home}/plugins"
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
        # Hermes has used both keys across versions. Set both so status,
        # oneshot, and TUI all resolve the intended Docker default.
        text = upsert_scalar(text, "default", model)
        text = upsert_scalar(text, "model", model)
    if provider:
        text = upsert_scalar(text, "provider", provider)
    p.write_text(text)
PY
fi

# Initialize GBrain's local PGLite brain on first container start. This is
# idempotent; persistent data lives in the partner's /root volume under
# /root/.gbrain.
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
  if [[ "${GBRAIN_MOCK_IMPORT_ON_START:-true}" == "true" ]]; then
    mock_source="${GBRAIN_MOCK_SOURCE:-}"
    mock_marker="${gbrain_config_dir}/${GBRAIN_MOCK_IMPORT_MARKER:-.mock-corpus-imported}"
    if [[ -z "${mock_source}" ]]; then
      echo "GBRAIN_MOCK_SOURCE is not set; skipping mock GBrain import." >&2
    elif [[ ! -e "${mock_marker}" ]]; then
      if [[ -d "${mock_source}" ]]; then
        echo "Importing mock GBrain data for ${PARTNER_NAME:-Hermes} from ${mock_source}..."
        if gbrain import "${mock_source}" --no-embed; then
          touch "${mock_marker}" || true
        else
          echo "Failed to import mock GBrain data from ${mock_source}" >&2
        fi
      else
        echo "Mock GBrain data not found: ${mock_source}" >&2
      fi
    fi
  fi
fi

if [[ "${A2A_ENABLED:-false}" == "true" ]]; then
  python3 /opt/a2a/a2a_server.py &
  echo "a2a sidecar started on ${A2A_BIND:-127.0.0.1}:${A2A_PORT:-8080}"
fi

if [[ -n "${HERMES_COMMAND:-}" ]]; then
  echo "Starting Hermes agent: ${HERMES_COMMAND}"
  bash -lc "${HERMES_COMMAND}" &
  child_pid=$!
  wait "$child_pid"
else
  echo "HERMES_COMMAND is not set. Container will stay alive."
  echo "Exec into it with: docker compose exec <partner-service> bash"
  tail -f /dev/null &
  child_pid=$!
  wait "$child_pid"
fi
