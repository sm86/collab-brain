#!/usr/bin/env python3
import concurrent.futures
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

try:
    import yaml
except ImportError:  # pragma: no cover - Docker image installs PyYAML.
    yaml = None


ROUTER_VERSION = "0.1.0"
MCP_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_SKILL = "company-info"


class BadRequest(Exception):
    pass


def env_int(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[collab-router] invalid {name}={raw!r}; using {default}", file=sys.stderr)
        return default


def json_bytes(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def normalize_key(value):
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def default_config():
    partners = {
        "garry": {"a2a_url": "http://hermes-garry:8080"},
        "monica": {"a2a_url": "http://hermes-monica:8080"},
        "laurie": {"a2a_url": "http://hermes-laurie:8080"},
    }
    callers = {}
    for caller in partners:
        callers[caller] = {
            "can_ask": [partner for partner in partners if partner != caller],
            "skills": [DEFAULT_SKILL],
        }
    return {
        "caller": os.environ.get("ROUTER_CALLER", "garry"),
        "partners": partners,
        "default_skill": DEFAULT_SKILL,
        "timeout_seconds": env_int("ROUTER_TIMEOUT_SECONDS", 90),
        "max_concurrency": env_int("ROUTER_MAX_CONCURRENCY", 1),
        "policy": {
            "require_purpose": True,
            "deny_self_calls": True,
            "callers": callers,
        },
    }


def load_config(path):
    cfg = default_config()
    if not path:
        return cfg
    if not os.path.exists(path):
        print(f"[collab-router] config not found: {path}; using defaults", file=sys.stderr)
        return cfg
    with open(path, "r", encoding="utf-8") as fh:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load ROUTER_CONFIG")
        loaded = yaml.safe_load(fh) or {}
    cfg.update(loaded)
    cfg["caller"] = os.environ.get("ROUTER_CALLER", cfg.get("caller", "garry"))
    cfg["default_skill"] = cfg.get("default_skill") or DEFAULT_SKILL
    cfg["timeout_seconds"] = int(
        os.environ.get("ROUTER_TIMEOUT_SECONDS", cfg.get("timeout_seconds", 90))
    )
    cfg["max_concurrency"] = int(
        os.environ.get("ROUTER_MAX_CONCURRENCY", cfg.get("max_concurrency", 1))
    )
    return cfg


def router_mcp_token(caller):
    token = os.environ.get("COLLAB_ROUTER_MCP_TOKEN", "")
    if token:
        return token
    env_name = f"COLLAB_ROUTER_{caller.upper()}_MCP_TOKEN"
    return os.environ.get(env_name, "")


@dataclass
class Router:
    config: dict
    mcp_token: str = ""
    a2a_token: str = ""

    @property
    def caller(self):
        return normalize_key(self.config.get("caller"))

    @property
    def skill(self):
        return normalize_key(self.config.get("default_skill")) or DEFAULT_SKILL

    @property
    def timeout(self):
        return int(self.config.get("timeout_seconds") or 90)

    @property
    def max_concurrency(self):
        return max(1, int(self.config.get("max_concurrency") or 1))

    def ask_partner_brain(self, arguments):
        partner = normalize_key(arguments.get("partner"))
        company_query = (arguments.get("company_query") or "").strip()
        purpose = (arguments.get("purpose") or "").strip()
        return self._ask_one(partner, company_query, purpose)

    def ask_partner_brains(self, arguments):
        raw_partners = arguments.get("partners")
        if not isinstance(raw_partners, list):
            return {
                "status": "rejected",
                "skill": self.skill,
                "results": [
                    self._rejected("", "partners must be a non-empty array"),
                ],
            }

        partners = []
        seen = set()
        for raw in raw_partners:
            partner = normalize_key(raw)
            if partner and partner not in seen:
                partners.append(partner)
                seen.add(partner)

        company_query = (arguments.get("company_query") or "").strip()
        purpose = (arguments.get("purpose") or "").strip()
        if not partners:
            return {
                "status": "rejected",
                "skill": self.skill,
                "results": [self._rejected("", "partners must be a non-empty array")],
            }

        results_by_partner = {}
        rejected = []
        allowed = []
        for partner in partners:
            reason = self.policy_rejection_reason(partner, company_query, purpose)
            if reason:
                result = self._rejected(partner, reason)
                rejected.append(result)
                results_by_partner[partner] = result
            else:
                allowed.append(partner)

        max_workers = min(self.max_concurrency, max(1, len(allowed)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.forward_to_a2a, partner, company_query, purpose): partner
                for partner in allowed
            }
            for future in concurrent.futures.as_completed(futures):
                partner = futures[future]
                try:
                    results_by_partner[partner] = future.result()
                except Exception as exc:
                    results_by_partner[partner] = self._upstream_error(
                        partner, f"target A2A endpoint failed: {exc}"
                    )

        results = [results_by_partner[partner] for partner in partners]
        return {
            "status": batch_status(results),
            "skill": self.skill,
            "results": results,
        }

    def _ask_one(self, partner, company_query, purpose):
        reason = self.policy_rejection_reason(partner, company_query, purpose)
        if reason:
            result = self._rejected(partner, reason)
            log_decision(self.caller, partner, self.skill, result["status"], reason, 0)
            return result
        return self.forward_to_a2a(partner, company_query, purpose)

    def policy_rejection_reason(self, partner, company_query, purpose):
        if not self.caller:
            return "unknown caller"
        if partner not in self.config.get("partners", {}):
            return f"unknown target partner: {partner or '<empty>'}"
        if not company_query:
            return "company_query is required"

        policy = self.config.get("policy", {})
        if policy.get("require_purpose", True) and not purpose:
            return "purpose is required"
        if policy.get("deny_self_calls", True) and partner == self.caller:
            return "self calls are not allowed"

        caller_policy = (policy.get("callers") or {}).get(self.caller)
        if not caller_policy:
            return f"unknown caller: {self.caller}"
        if self.skill not in caller_policy.get("skills", []):
            return f"{self.caller} is not allowed to use skill {self.skill}"
        if partner not in caller_policy.get("can_ask", []):
            return f"{self.caller} is not allowed to ask {partner} for this skill"
        return ""

    def forward_to_a2a(self, partner, company_query, purpose):
        partner_cfg = self.config.get("partners", {}).get(partner, {})
        base_url = str(partner_cfg.get("a2a_url", "")).rstrip("/")
        if not base_url:
            return self._upstream_error(partner, f"missing A2A URL for {partner}")

        body = {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_USER",
                "parts": [{"text": company_query}],
            },
            "metadata": {
                "caller": self.caller,
                "target": partner,
                "skill": self.skill,
                "purpose": purpose,
            },
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.a2a_token:
            headers["Authorization"] = f"Bearer {self.a2a_token}"
        req = request.Request(
            f"{base_url}/message:send",
            data=json_bytes(body),
            headers=headers,
            method="POST",
        )

        started = time.monotonic()
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except error.HTTPError as exc:
            reason = f"target A2A endpoint returned HTTP {exc.code}"
            log_decision(self.caller, partner, self.skill, "upstream_error", reason, elapsed_ms(started))
            return self._upstream_error(partner, reason)
        except TimeoutError:
            reason = "target A2A endpoint timed out"
            log_decision(self.caller, partner, self.skill, "upstream_error", reason, elapsed_ms(started))
            return self._upstream_error(partner, reason)
        except Exception as exc:
            reason = f"target A2A endpoint failed: {exc}"
            log_decision(self.caller, partner, self.skill, "upstream_error", reason, elapsed_ms(started))
            return self._upstream_error(partner, reason)

        text = extract_a2a_text(data)
        if not text:
            reason = "target A2A response did not include text"
            log_decision(self.caller, partner, self.skill, "upstream_error", reason, elapsed_ms(started))
            return self._upstream_error(partner, reason)
        log_decision(self.caller, partner, self.skill, "ok", "policy allow", elapsed_ms(started))
        return {
            "status": "ok",
            "partner": partner,
            "skill": self.skill,
            "text": text,
        }

    def _rejected(self, partner, reason):
        return {
            "status": "rejected",
            "partner": partner,
            "skill": self.skill,
            "reason": reason,
        }

    def _upstream_error(self, partner, reason):
        return {
            "status": "upstream_error",
            "partner": partner,
            "skill": self.skill,
            "reason": reason,
        }


def batch_status(results):
    statuses = [item.get("status") for item in results]
    if statuses and all(status == "ok" for status in statuses):
        return "ok"
    if any(status == "ok" for status in statuses):
        return "partial"
    if statuses and all(status == "rejected" for status in statuses):
        return "rejected"
    return "upstream_error"


def elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


def extract_a2a_text(data):
    message = data.get("message") if isinstance(data, dict) else None
    parts = message.get("parts") if isinstance(message, dict) else None
    if not isinstance(parts, list):
        return ""
    texts = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts).strip()


def log_decision(caller, target, skill, status, reason, duration_ms):
    event = {
        "event": "router_decision",
        "caller": caller,
        "target": target,
        "skill": skill,
        "status": status,
        "reason": reason,
        "duration_ms": duration_ms,
    }
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr)
    emit_dashboard_event(event)


def emit_dashboard_event(event):
    url = os.environ.get("DASHBOARD_EVENTS_URL", "").strip()
    if not url:
        return
    req = request.Request(
        url,
        data=json_bytes(event),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=1.0):
            return
    except Exception:
        return


TOOL_SCHEMAS = [
    {
        "name": "ask_partner_brain",
        "description": "Ask one configured partner's local brain for company context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "partner": {"type": "string", "description": "Target partner key."},
                "company_query": {"type": "string", "description": "Company name or concise query."},
                "purpose": {"type": "string", "description": "Why this partner context is needed."},
            },
            "required": ["partner", "company_query", "purpose"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ask_partner_brains",
        "description": "Ask multiple configured partner brains in parallel for company context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "partners": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target partner keys.",
                },
                "company_query": {"type": "string", "description": "Company name or concise query."},
                "purpose": {"type": "string", "description": "Why this partner context is needed."},
            },
            "required": ["partners", "company_query", "purpose"],
            "additionalProperties": False,
        },
    },
]


def mcp_response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def mcp_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_mcp_rpc(router, payload):
    if not isinstance(payload, dict):
        return mcp_error(None, -32600, "Invalid Request")
    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if req_id is None:
        return None
    if method == "initialize":
        protocol_version = params.get("protocolVersion") or MCP_PROTOCOL_VERSION
        return mcp_response(
            req_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "collab-router", "version": ROUTER_VERSION},
            },
        )
    if method == "ping":
        return mcp_response(req_id, {})
    if method == "tools/list":
        return mcp_response(req_id, {"tools": TOOL_SCHEMAS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return mcp_error(req_id, -32602, "arguments must be an object")
        if name == "ask_partner_brain":
            result = router.ask_partner_brain(arguments)
        elif name == "ask_partner_brains":
            result = router.ask_partner_brains(arguments)
        else:
            return mcp_error(req_id, -32601, f"Unknown tool: {name}")
        return mcp_response(
            req_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2, sort_keys=True),
                    }
                ],
                "isError": False,
            },
        )
    return mcp_error(req_id, -32601, f"Method not found: {method}")


class RouterHandler(BaseHTTPRequestHandler):
    server_version = "CollabRouter/0.1"

    def do_GET(self):
        if self.path == "/healthz":
            self.send_json(200, {"status": "ok", "caller": self.server.router.caller})
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/mcp":
            self.send_json(404, {"error": "not found"})
            return
        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return
        try:
            payload = self.read_json_body()
            response = self.handle_payload(payload)
        except BadRequest:
            self.send_json(400, {"error": "bad request"})
            return
        except Exception as exc:
            print(f"[collab-router] internal error: {exc}", file=sys.stderr)
            self.send_json(500, {"error": "internal error"})
            return

        if response is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_json(200, response)

    def handle_payload(self, payload):
        router = self.server.router
        if isinstance(payload, list):
            responses = [handle_mcp_rpc(router, item) for item in payload]
            return [item for item in responses if item is not None] or None
        return handle_mcp_rpc(router, payload)

    def authorized(self):
        token = self.server.router.mcp_token
        if not token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {token}"

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise BadRequest() from exc
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise BadRequest() from exc

    def send_json(self, status, body):
        payload = json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        elapsed = elapsed_ms(getattr(self, "_started_at", time.monotonic()))
        print(
            f"[collab-router] {self.command} {self.path} status={args[1] if len(args) > 1 else '-'} ms={elapsed}",
            file=sys.stderr,
        )

    def handle_one_request(self):
        self._started_at = time.monotonic()
        super().handle_one_request()


def main():
    bind = os.environ.get("ROUTER_BIND", "0.0.0.0")
    port = env_int("ROUTER_PORT", 8090)
    config = load_config(os.environ.get("ROUTER_CONFIG", ""))
    router = Router(
        config=config,
        mcp_token=router_mcp_token(normalize_key(config.get("caller"))),
        a2a_token=os.environ.get("A2A_ROUTER_TOKEN", ""),
    )
    server = ThreadingHTTPServer((bind, port), RouterHandler)
    server.router = router
    print(
        f"[collab-router] serving caller={router.caller} on {bind}:{port}",
        file=sys.stderr,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
