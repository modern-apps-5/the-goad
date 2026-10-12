#!/usr/bin/env python3
"""Create the runner's GitHub App, and save its ID and private key.

GitHub has no API that creates an App outright. A person must confirm it in a
browser, once. This serves a form that carries the App's settings, catches
GitHub's redirect, and trades the code in it for the App's ID and key.

    scripts/create-github-app.py

Then open http://localhost:8765/ in a browser on this machine, signed in to
GitHub as an owner of the organization. From another machine, first run
`ssh -L 8765:localhost:8765 <this machine>`.

It prints the App's ID, for github_app_id in lab.auto.tfvars, and writes
the private key to terraform/runner/.secrets/private-key.pem, which git
ignores. It prints no secret. Needs `gh`.
"""
import html, http.server, json, os, pathlib, re, secrets, subprocess, urllib.parse

ORG = "modern-apps-5"
PORT = 8765
# Where terraform/runner reads the key from.
OUT = pathlib.Path(__file__).resolve().parent.parent / "terraform/runner/.secrets"
STATE = secrets.token_urlsafe(16)

# All the App needs: to register runners for the organization. No webhook.
MANIFEST = {
    "name": "goad-supervisor-runner",
    "url": f"https://github.com/{ORG}/the-goad",
    "hook_attributes": {"url": "https://example.com/unused", "active": False},
    "redirect_url": f"http://localhost:{PORT}/callback",
    "public": False,
    "default_permissions": {"organization_self_hosted_runners": "write"},
    "default_events": [],
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def page(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            self.page(200, f"""<form id=f method=post
  action="https://github.com/organizations/{ORG}/settings/apps/new?state={STATE}">
<input type=hidden name=manifest value="{html.escape(json.dumps(MANIFEST))}">
<button>Create the GitHub App</button></form>
<script>document.getElementById('f').submit()</script>""")
        elif url.path == "/callback":
            code = query.get("code", [""])[0]
            if query.get("state", [""])[0] != STATE or not re.fullmatch(r"[A-Za-z0-9_-]+", code):
                return self.page(400, "The state or the code is wrong. Start again.")
            result = subprocess.run(
                ["gh", "api", "-X", "POST", f"/app-manifests/{code}/conversions"],
                capture_output=True, text=True)
            if result.returncode:
                print("GitHub refused the code:", result.stderr.strip()[:300], flush=True)
                return self.page(500, "GitHub refused the code. See the terminal.")
            app = json.loads(result.stdout)
            OUT.mkdir(mode=0o700, exist_ok=True)
            key = os.open(OUT / "private-key.pem", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.write(key, app["pem"].encode())
            os.close(key)
            print(f"Created the App {app['slug']}. Now install it, in the browser.", flush=True)
            print(f"Then put this in lab.auto.tfvars:  github_app_id = \"{app['id']}\"", flush=True)
            # Creating an App does not install it. Send the browser there.
            self.send_response(302)
            self.send_header("Location", f"https://github.com/apps/{app['slug']}/installations/new")
            self.end_headers()
            self.server.done = True
        else:
            self.page(404, "Not found.")


server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
server.done = False
print(f"Open http://localhost:{PORT}/", flush=True)
while not server.done:
    server.handle_request()
