#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DASHBOARD_BIND = os.environ.get("DASHBOARD_BIND", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8095"))
AGENT_CARD_TIMEOUT = float(os.environ.get("DASHBOARD_AGENT_CARD_TIMEOUT", "2.5"))
MAX_EVENTS = int(os.environ.get("DASHBOARD_MAX_EVENTS", "100"))

DEFAULT_PARTNERS = {
    "garry": {
        "name": "Garry",
        "a2a_url": "http://hermes-garry:8080",
    },
    "monica": {
        "name": "Monica",
        "a2a_url": "http://hermes-monica:8080",
    },
    "laurie": {
        "name": "Laurie",
        "a2a_url": "http://hermes-laurie:8080",
    },
}

DEFAULT_POLICY = {
    "label": "Demo Policy",
    "description": (
        "Own brains are local. Garry can access Monica and Laurie; Monica can "
        "access Laurie; Laurie cannot access Monica or Garry."
    ),
    "callers": {
        "garry": {"can_ask": ["monica", "laurie"], "skills": ["company-info"]},
        "monica": {"can_ask": ["laurie"], "skills": ["company-info"]},
        "laurie": {"can_ask": [], "skills": ["company-info"]},
    },
}

STATE = {
    "policy": json.loads(json.dumps(DEFAULT_POLICY)),
    "events": deque(maxlen=MAX_EVENTS),
    "started_at": time.time(),
}


def load_partners():
    raw = os.environ.get("DASHBOARD_PARTNERS_JSON", "").strip()
    if not raw:
        return DEFAULT_PARTNERS
    try:
        partners = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_PARTNERS
    if not isinstance(partners, dict):
        return DEFAULT_PARTNERS
    clean = {}
    for key, value in partners.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        name = value.get("name")
        a2a_url = value.get("a2a_url")
        if isinstance(name, str) and isinstance(a2a_url, str):
            clean[key] = {"name": name, "a2a_url": a2a_url.rstrip("/")}
    return clean or DEFAULT_PARTNERS


PARTNERS = load_partners()


def json_bytes(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def read_json_url(url, timeout):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return response.status, json.loads(raw.decode("utf-8"))


def fetch_agent_card(partner_key, partner):
    base_url = partner["a2a_url"].rstrip("/")
    result = {
        "partner": partner_key,
        "name": partner["name"],
        "a2a_url": base_url,
        "health": "unknown",
        "card_status": "unknown",
        "skills": [],
        "card": None,
        "error": None,
    }

    try:
        status, health = read_json_url(f"{base_url}/healthz", AGENT_CARD_TIMEOUT)
        result["health"] = "ok" if status == 200 and health.get("status") == "ok" else "degraded"
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        result["health"] = "unreachable"
        result["error"] = f"health check failed: {exc}"

    try:
        status, card = read_json_url(
            f"{base_url}/.well-known/agent-card.json",
            AGENT_CARD_TIMEOUT,
        )
        if status != 200 or not isinstance(card, dict):
            raise ValueError(f"unexpected agent card status {status}")
        skills = []
        for skill in card.get("skills", []):
            if isinstance(skill, dict):
                skills.append(
                    {
                        "id": skill.get("id", "unknown"),
                        "name": skill.get("name", "Unknown skill"),
                        "description": skill.get("description", ""),
                    }
                )
        result.update(
            {
                "card_status": "ok",
                "card": card,
                "skills": skills,
                "protocol": card.get("supportedInterfaces", [{}])[0].get("protocolBinding"),
            }
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        result["card_status"] = "unreachable"
        if not result["error"]:
            result["error"] = f"agent card failed: {exc}"
    return result


def reset_policy():
    STATE["policy"] = json.loads(json.dumps(DEFAULT_POLICY))
    return STATE["policy"]


def set_access(caller, target, skill, enabled):
    caller = (caller or "").strip().lower()
    target = (target or "").strip().lower()
    skill = (skill or "company-info").strip()
    if caller not in PARTNERS:
        return False, f"unknown caller: {caller or '<empty>'}"
    if target not in PARTNERS:
        return False, f"unknown target: {target or '<empty>'}"
    if caller == target:
        return False, "local routes are always available and are not editable"
    if skill != "company-info":
        return False, f"unknown skill: {skill}"

    caller_policy = STATE["policy"]["callers"].setdefault(
        caller,
        {"can_ask": [], "skills": ["company-info"]},
    )
    allowed = caller_policy.setdefault("can_ask", [])
    if enabled and target not in allowed:
        allowed.append(target)
    if not enabled and target in allowed:
        allowed.remove(target)
    return True, "policy allow" if enabled else "policy blocked"


def route_status(caller, target, skill="company-info"):
    if caller == target:
        return {
            "caller": caller,
            "target": target,
            "skill": skill,
            "status": "local",
            "reason": "own brain; no router needed",
        }

    caller_policy = STATE["policy"]["callers"].get(caller, {})
    can_ask = caller_policy.get("can_ask", [])
    skills = caller_policy.get("skills", [])
    allowed = target in can_ask and skill in skills
    return {
        "caller": caller,
        "target": target,
        "skill": skill,
        "status": "allowed" if allowed else "blocked",
        "reason": "policy allow" if allowed else "policy blocked",
    }


def access_matrix():
    keys = list(PARTNERS.keys())
    return {
        "callers": keys,
        "targets": keys,
        "skill": "company-info",
        "routes": [route_status(caller, target) for caller in keys for target in keys],
    }


def add_event(event):
    now = time.time()
    clean = {
        "id": f"evt-{int(now * 1000)}-{len(STATE['events'])}",
        "timestamp": now,
        "event": event.get("event", "router_event"),
        "caller": event.get("caller"),
        "target": event.get("target"),
        "skill": event.get("skill", "company-info"),
        "status": event.get("status"),
        "reason": event.get("reason"),
        "duration_ms": event.get("duration_ms"),
    }
    STATE["events"].appendleft(clean)
    return clean


def state_payload(include_cards=False):
    payload = {
        "policy_mode": "demo",
        "policy": STATE["policy"],
        "partners": PARTNERS,
        "access_matrix": access_matrix(),
        "events": list(STATE["events"]),
        "uptime_seconds": int(time.time() - STATE["started_at"]),
    }
    if include_cards:
        payload["agent_cards"] = [
            fetch_agent_card(key, partner) for key, partner in PARTNERS.items()
        ]
    return payload


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Collab Router Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --line: #d9dee8;
      --text: #172033;
      --muted: #667085;
      --good: #087443;
      --good-bg: #dff7e9;
      --bad: #9f1d2f;
      --bad-bg: #ffe3e7;
      --warn: #915c00;
      --warn-bg: #fff1ce;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 20px; letter-spacing: 0; }
    h2 { margin: 0 0 12px; font-size: 15px; letter-spacing: 0; }
    main {
      padding: 20px 24px 32px;
      display: grid;
      gap: 18px;
    }
    .toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }
    button.active { background: #172033; color: #fff; border-color: #172033; }
    .grid { display: grid; gap: 14px; }
    .cards { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
    .policy-note {
      color: var(--muted);
      font-size: 13px;
      max-width: 760px;
    }
    .hierarchy {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin: 4px 0 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .node {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 6px 10px;
      font-weight: 800;
    }
    .arrow { color: #98a2b3; font-weight: 900; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .agent-card {
      min-height: 168px;
      display: grid;
      align-content: start;
      gap: 10px;
    }
    .agent-title { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .agent-title strong { font-size: 18px; }
    .meta { color: var(--muted); font-size: 12px; word-break: break-word; }
    .badges { display: flex; flex-wrap: wrap; gap: 6px; }
    .badge {
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .ok { color: var(--good); background: var(--good-bg); }
    .blocked, .error { color: var(--bad); background: var(--bad-bg); }
    .local { color: #475467; background: #eef1f5; }
    .unknown { color: var(--warn); background: var(--warn-bg); }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td { border: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; background: #fafbfc; }
    td.allowed-cell { background: var(--good-bg); color: var(--good); font-weight: 800; }
    td.blocked-cell { background: var(--bad-bg); color: var(--bad); font-weight: 800; }
    td.local-cell { background: #eef1f5; color: #475467; font-weight: 800; }
    .toggle-row {
      margin-top: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    .timeline { display: grid; gap: 8px; }
    .event {
      border: 1px solid var(--line);
      border-left-width: 5px;
      border-radius: 6px;
      background: #fff;
      padding: 10px 12px;
      display: grid;
      gap: 4px;
    }
    .event.ok { border-left-color: var(--good); background: #fff; }
    .event.blocked, .event.error { border-left-color: var(--bad); background: #fff; }
    .event .title { font-weight: 800; }
    .event .detail { color: var(--muted); font-size: 12px; }
    @media (min-width: 1020px) {
      .lower { grid-template-columns: 1.1fr .9fr; align-items: start; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Collab Router Dashboard</h1>
      <div class="meta">Agent cards, demo policy, and live router decisions</div>
    </div>
    <div class="toolbar" id="policyControls"></div>
  </header>
  <main>
    <section>
      <h2>Agent Cards</h2>
      <div class="grid cards" id="agentCards"></div>
    </section>
    <section class="grid lower">
      <div class="panel">
        <h2>Demo Policy</h2>
        <div class="policy-note" id="policyNote"></div>
        <div class="hierarchy" aria-label="Org hierarchy">
          <span class="node">Garry</span><span class="arrow">-></span><span class="node">Monica</span><span class="arrow">-></span><span class="node">Laurie</span>
        </div>
        <div id="matrix"></div>
      </div>
      <div class="panel">
        <h2>Live Timeline</h2>
        <div class="timeline" id="timeline"></div>
      </div>
    </section>
  </main>
  <script>
    let cardsLoaded = false;
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));

    async function resetPolicy() {
      await fetch('/admin/policy/reset', {method: 'POST'});
      await refresh(false);
    }

    async function toggleAccess(caller, target, skill, enabled) {
      await fetch('/admin/access', {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({caller, target, skill, enabled})
      });
      await refresh(false);
    }

    function renderPolicyControls(data) {
      document.getElementById('policyControls').innerHTML = '<button onclick="resetPolicy()">Reset hierarchy</button>';
      document.getElementById('policyNote').textContent = data.policy.description;
    }

    function renderCards(cards) {
      const root = document.getElementById('agentCards');
      root.innerHTML = cards.map(card => {
        const healthClass = card.health === 'ok' ? 'ok' : (card.health === 'unreachable' ? 'error' : 'unknown');
        const cardClass = card.card_status === 'ok' ? 'ok' : 'error';
        const skills = card.skills.length ? card.skills.map(s => `<span class="badge ok">${esc(s.id)}</span>`).join('') : '<span class="meta">No skills available</span>';
        return `<article class="panel agent-card">
          <div class="agent-title"><strong>${esc(card.name)}</strong><span class="badge ${healthClass}">${esc(card.health)}</span></div>
          <div class="meta">${esc(card.partner)} · ${esc(card.a2a_url)}</div>
          <div class="badges"><span class="badge ${cardClass}">agent card ${esc(card.card_status)}</span>${card.protocol ? `<span class="badge unknown">${esc(card.protocol)}</span>` : ''}</div>
          <div class="badges">${skills}</div>
          ${card.error ? `<div class="meta">${esc(card.error)}</div>` : ''}
        </article>`;
      }).join('');
    }

    function renderMatrix(matrix) {
      const routeMap = new Map(matrix.routes.map(route => [`${route.caller}:${route.target}`, route]));
      let html = '<table><thead><tr><th>Caller</th>';
      html += matrix.targets.map(target => `<th>${esc(target)}</th>`).join('');
      html += '</tr></thead><tbody>';
      for (const caller of matrix.callers) {
        html += `<tr><th>${esc(caller)}</th>`;
        for (const target of matrix.targets) {
          const route = routeMap.get(`${caller}:${target}`);
          const labels = {allowed: 'Allowed', blocked: 'Blocked', local: 'Local'};
          const cellClass = route.status === 'allowed' ? 'allowed-cell' : (route.status === 'local' ? 'local-cell' : 'blocked-cell');
          const toggle = route.status === 'local' ? '' : `<label class="toggle-row"><input type="checkbox" ${route.status === 'allowed' ? 'checked' : ''} onchange="toggleAccess('${esc(caller)}','${esc(target)}','${esc(route.skill)}',this.checked)"> company-info</label>`;
          html += `<td class="${cellClass}">${labels[route.status] || esc(route.status)}<div class="meta">${esc(route.reason)}</div>${toggle}</td>`;
        }
        html += '</tr>';
      }
      html += '</tbody></table>';
      document.getElementById('matrix').innerHTML = html;
    }

    function renderTimeline(events) {
      const root = document.getElementById('timeline');
      if (!events.length) {
        root.innerHTML = '<div class="meta">No router events yet.</div>';
        return;
      }
      root.innerHTML = events.map(event => {
        const statusClass = event.status === 'ok' || event.status === 'allowed' ? 'ok' : (event.status === 'local' ? 'local' : (event.status === 'blocked' || event.status === 'rejected' || event.status === 'upstream_error' ? 'blocked' : 'unknown'));
        const when = new Date(event.timestamp * 1000).toLocaleTimeString();
        return `<div class="event ${statusClass}">
          <div class="title">${esc(event.event)} · ${esc(event.status ?? 'pending')}</div>
          <div class="detail">${esc(when)} · ${esc(event.caller ?? '-')} -> ${esc(event.target ?? '-')} · ${esc(event.skill ?? '-')}</div>
          <div class="detail">${esc(event.reason ?? '')}${event.duration_ms != null ? ` · ${esc(event.duration_ms)}ms` : ''}</div>
        </div>`;
      }).join('');
    }

    async function refresh(includeCards = false) {
      const state = await fetch('/admin/state' + (includeCards ? '?include_cards=1' : '')).then(r => r.json());
      renderPolicyControls(state);
      renderMatrix(state.access_matrix);
      renderTimeline(state.events);
      if (includeCards || !cardsLoaded) {
        const cards = state.agent_cards || await fetch('/admin/agent-cards').then(r => r.json()).then(r => r.agent_cards);
        renderCards(cards);
        cardsLoaded = true;
      }
    }

    refresh(true);
    setInterval(() => refresh(false), 1500);
    setInterval(() => fetch('/admin/agent-cards').then(r => r.json()).then(r => renderCards(r.agent_cards)), 10000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CollabDashboard/0.1"

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/":
            self.send_html(200, INDEX_HTML)
            return
        if path == "/healthz":
            self.send_json(200, {"status": "ok"})
            return
        if path == "/admin/state":
            self.send_json(200, state_payload(include_cards="include_cards=1" in query))
            return
        if path == "/admin/agent-cards":
            self.send_json(
                200,
                {
                    "agent_cards": [
                        fetch_agent_card(key, partner) for key, partner in PARTNERS.items()
                    ]
                },
            )
            return
        if path == "/admin/events":
            self.send_json(200, {"events": list(STATE["events"])})
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/admin/policy/reset":
            reset_policy()
            add_event(
                {
                    "event": "policy_reset",
                    "status": "ok",
                    "reason": "reset demo policy hierarchy",
                }
            )
            self.send_json(200, state_payload())
            return

        if self.path == "/admin/events":
            event = add_event(self.read_json_body())
            self.send_json(201, {"event": event})
            return

        if self.path == "/admin/demo-request":
            body = self.read_json_body()
            caller = body.get("caller", "garry")
            targets = body.get("targets", ["monica", "laurie"])
            created = []
            for target in targets:
                route = route_status(caller, target)
                if route["status"] == "local":
                    status = "local"
                else:
                    status = "allowed" if route["status"] == "allowed" else "rejected"
                created.append(
                    add_event(
                        {
                            "event": "router_decision",
                            "caller": caller,
                            "target": target,
                            "skill": route["skill"],
                            "status": status,
                            "reason": route["reason"],
                        }
                    )
                )
                if status == "allowed":
                    created.append(
                        add_event(
                            {
                                "event": "a2a_call_succeeded",
                                "caller": caller,
                                "target": target,
                                "skill": route["skill"],
                                "status": "ok",
                                "reason": "demo call completed",
                                "duration_ms": 1200,
                            }
                        )
                    )
            self.send_json(201, {"events": created})
            return

        self.send_json(404, {"error": "not found"})

    def do_PATCH(self):
        if self.path != "/admin/access":
            self.send_json(404, {"error": "not found"})
            return

        body = self.read_json_body()
        caller = body.get("caller")
        target = body.get("target")
        skill = body.get("skill", "company-info")
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            self.send_json(400, {"error": "enabled must be boolean"})
            return

        ok, reason = set_access(caller, target, skill, enabled)
        if not ok:
            self.send_json(400, {"error": reason})
            return

        event = add_event(
            {
                "event": "policy_updated",
                "caller": caller,
                "target": target,
                "skill": skill,
                "status": "allowed" if enabled else "blocked",
                "reason": reason,
            }
        )
        self.send_json(200, {"event": event, "access_matrix": access_matrix()})

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def send_json(self, status, body):
        payload = json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_html(self, status, body):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        return


def main():
    server = ThreadingHTTPServer((DASHBOARD_BIND, DASHBOARD_PORT), DashboardHandler)
    print(f"[dashboard] serving on {DASHBOARD_BIND}:{DASHBOARD_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
