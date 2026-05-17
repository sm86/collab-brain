#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SIDECAR_VERSION = "0.1.0"
A2A_PROTOCOL_VERSION = "1.0"

PROMPT_TEMPLATE = """\
You are a YC partner. A peer agent is asking what YOU know about a company
so they can prepare for a meeting. Answer ONLY from the notes below -- your
personal brain. Do not invent details. If the notes are empty or unrelated,
say plainly that you have no record of this company.

Return a concise briefing covering, as available:
- Past interactions (meetings, emails, threads -- with dates if known)
- Key contacts and their roles
- What the company is working on / current state
- Your assessment and any open risks or unanswered questions

=== Brain notes ===
{brain_notes}
=== End brain notes ===

Company query from peer agent:
{user_query}
"""


def env_int(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"[a2a] invalid {name}={raw!r}; using {default}", file=sys.stderr)
        return default
    return value


A2A_BIND = os.environ.get("A2A_BIND", "127.0.0.1")
A2A_PORT = env_int("A2A_PORT", 8080)
A2A_PUBLIC_URL = os.environ.get("A2A_PUBLIC_URL") or f"http://localhost:{A2A_PORT}"
A2A_HERMES_TIMEOUT = env_int("A2A_HERMES_TIMEOUT", 90)
A2A_GBRAIN_TIMEOUT = env_int("A2A_GBRAIN_TIMEOUT", 15)
A2A_ROUTER_TOKEN = os.environ.get("A2A_ROUTER_TOKEN", "")
GBRAIN_SNIPPET_LIMIT = 20
GBRAIN_PAGE_LIMIT = 8

AGENT_CARD = {
    "name": "Hermes",
    "description": (
        "Hermes Agent CLI exposed over A2A. Forwards a company-info query to "
        "the agent's GBrain and returns brain-grounded notes about the company."
    ),
    "version": SIDECAR_VERSION,
    "supportedInterfaces": [
        {
            "url": A2A_PUBLIC_URL,
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": A2A_PROTOCOL_VERSION,
        }
    ],
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "id": "company-info",
            "name": "Company info from brain",
            "description": (
                "Given a company name or query, returns what this agent's brain "
                "knows about that company -- past interactions, key contacts, "
                "what they're working on, current status, and open risks -- "
                "drawn from notes, meetings, and company entries in the "
                "agent's GBrain."
            ),
            "tags": ["company-info", "brain", "crm", "notes", "briefing"],
            "examples": [
                "Acme",
                "What do you know about Acme?",
                "Give me a briefing on Stripe based on our past meetings.",
            ],
        }
    ],
}


class BadRequest(Exception):
    pass


def json_bytes(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def extract_user_query(body):
    if not isinstance(body, dict):
        raise BadRequest()
    message = body.get("message")
    if not isinstance(message, dict):
        raise BadRequest()
    if message.get("role") != "ROLE_USER":
        raise BadRequest()
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise BadRequest()

    texts = []
    content_keys = {"text", "raw", "url", "data"}
    for part in parts:
        if not isinstance(part, dict):
            raise BadRequest()
        present = [key for key in content_keys if key in part]
        if present != ["text"]:
            raise BadRequest()
        text = part.get("text")
        if not isinstance(text, str):
            raise BadRequest()
        texts.append(text)
    return "\n".join(texts)


def query_brain(user_query):
    query_result = run_gbrain(
        ["query", user_query, "--limit", str(GBRAIN_SNIPPET_LIMIT), "--detail", "medium"]
    )
    search_result = run_gbrain(["search", user_query])
    snippets = "\n".join(item for item in [query_result, search_result] if item).strip()
    slugs = extract_gbrain_slugs(snippets)
    pages = fetch_gbrain_pages(slugs[:GBRAIN_PAGE_LIMIT])

    sections = []
    if snippets:
        sections.append("=== Ranked snippets ===\n" + snippets)
    if pages:
        sections.append("=== Full pages ===\n" + "\n\n".join(pages))
    if sections:
        return "\n\n".join(sections)
    return "(no brain results)"


def run_gbrain(args):
    try:
        result = subprocess.run(
            ["gbrain", *args],
            capture_output=True,
            text=True,
            timeout=A2A_GBRAIN_TIMEOUT,
        )
    except Exception as exc:
        print(f"[a2a] gbrain failed: {exc}", file=sys.stderr)
        return ""

    stdout = result.stdout.strip()
    if result.returncode != 0 or not stdout:
        stderr = result.stderr.strip()
        print(
            f"[a2a] gbrain failed: status={result.returncode} stderr={stderr!r}",
            file=sys.stderr,
        )
        return ""
    return stdout


def extract_gbrain_slugs(text):
    slugs = []
    seen = set()
    for line in text.splitlines():
        match = re.match(r"^\[[^\]]+\]\s+([^\s]+)\s+--", line)
        if not match:
            continue
        slug = match.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


def fetch_gbrain_pages(slugs):
    pages = []
    for slug in slugs:
        body = run_gbrain(["get", slug])
        if not body:
            continue
        pages.append(f"--- Page: {slug} ---\n{body}")
    return pages


def call_hermes(prompt):
    try:
        result = subprocess.run(
            ["hermes", "chat", "-Q", "-q", prompt],
            capture_output=True,
            text=True,
            timeout=A2A_HERMES_TIMEOUT,
        )
    except Exception as exc:
        print(f"[a2a] hermes failed: {exc}", file=sys.stderr)
        return None

    stdout = result.stdout.strip()
    if result.returncode != 0 or not stdout:
        stderr = result.stderr.strip()
        print(
            f"[a2a] hermes failed: status={result.returncode} stderr={stderr!r}",
            file=sys.stderr,
        )
        return None
    return stdout


class A2AHandler(BaseHTTPRequestHandler):
    server_version = "HermesA2A/0.1"

    def do_GET(self):
        if self.path == "/healthz":
            self.send_json(200, {"status": "ok"})
            return
        if self.path == "/.well-known/agent-card.json":
            self.send_json(200, AGENT_CARD)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/message:send":
            self.send_json(404, {"error": "not found"})
            return
        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return
        try:
            body = self.read_json_body()
            user_query = extract_user_query(body)
            brain_notes = query_brain(user_query)
            prompt = PROMPT_TEMPLATE.format(
                brain_notes=brain_notes,
                user_query=user_query,
            )
            briefing = call_hermes(prompt)
            if not briefing:
                self.send_json(502, {"error": "hermes failed"})
                return
            self.send_json(
                200,
                {
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "ROLE_AGENT",
                        "parts": [{"text": briefing}],
                    }
                },
            )
        except BadRequest:
            self.send_json(400, {"error": "bad request"})
        except Exception as exc:
            print(f"[a2a] internal error: {exc}", file=sys.stderr)
            self.send_json(500, {"error": "internal error"})

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise BadRequest()
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise BadRequest() from exc

    def authorized(self):
        if not A2A_ROUTER_TOKEN:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {A2A_ROUTER_TOKEN}"

    def send_json(self, status, body):
        payload = json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        elapsed_ms = int((time.monotonic() - getattr(self, "_started_at", time.monotonic())) * 1000)
        print(
            f"[a2a] {self.command} {self.path} status={args[1] if len(args) > 1 else '-'} ms={elapsed_ms}",
            file=sys.stderr,
        )

    def handle_one_request(self):
        self._started_at = time.monotonic()
        super().handle_one_request()


def main():
    server = ThreadingHTTPServer((A2A_BIND, A2A_PORT), A2AHandler)
    print(f"[a2a] serving on {A2A_BIND}:{A2A_PORT}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
