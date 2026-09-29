#!/usr/bin/env python3
"""
HTML Table Generator: Paramount Digital
---------------------------------------
Serves the table generator and adds one helper endpoint for the "Site preset"
feature: it fetches a public web page plus its stylesheets so the tool can work
out the site's likely colours and fonts. Browsers can't read another site's
CSS directly (cross-origin rules), so this small local helper does the fetch.

Run:
    python app.py

Then open http://localhost:5732 (it opens automatically). Standard library only,
nothing to install. The tool still works as a plain index.html without this;
only the "Analyse site" button needs it.

Safety: binds to 127.0.0.1 only, only accepts requests from the tool itself,
refuses private/local network addresses (including via redirects), and caps
timeouts, file sizes and the number of stylesheets fetched.
"""

import ipaddress
import json
import re
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

PORT = 5732
ROOT = Path(__file__).resolve().parent
TIMEOUT = 12
MAX_HTML = 3_000_000
MAX_SHEET = 2_000_000
MAX_SHEETS = 20
MAX_TOTAL_CSS = 8_000_000
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36 ParamountTableGenerator/1.0")
ALLOWED_ORIGINS = {"null", f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}


class FetchError(Exception):
    pass


def check_url(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("Enter a full web address starting with http:// or https://")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise FetchError(f"Couldn't find {p.hostname}. Check the address is right.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise FetchError("That address is on a private or local network, so it can't be analysed.")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)  # every redirect hop must also be public
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SafeRedirect)


def fetch(url, limit, accept):
    check_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": accept, "Accept-Language": "en-GB,en;q=0.9"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            data = r.read(limit + 1)
            final = r.geturl()
            charset = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        hint = " The site may be blocking automated requests." if e.code in (401, 403, 429, 503) else ""
        raise FetchError(f"The site returned HTTP {e.code}.{hint}")
    except urllib.error.URLError as e:
        raise FetchError(f"Couldn't connect: {getattr(e, 'reason', e)}")
    except (socket.timeout, TimeoutError):
        raise FetchError("The site took too long to respond.")
    return data[:limit].decode(charset, errors="replace"), final, len(data) > limit


class PageCollector(HTMLParser):
    """Collects stylesheet links, <style> blocks, inline style attributes and theme-color."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.styles, self.inline = [], [], []
        self.theme_color = None
        self.title = ""
        self._in_style = self._in_title = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link":
            rel = a.get("rel", "").lower().split()
            media = a.get("media", "").lower()
            if a.get("href") and media != "print" and (
                    "stylesheet" in rel or ("preload" in rel and a.get("as", "").lower() == "style")):
                self.links.append(a["href"])
        elif tag == "style":
            self._in_style, self._buf = True, []
        elif tag == "title" and not self.title:  # page title only, not SVG <title>s later on
            self._in_title = True
        elif tag == "meta" and a.get("name", "").lower() == "theme-color":
            self.theme_color = a.get("content")
        if a.get("style") and len(self.inline) < 500:
            # keep the tag name so the analyser can tell a button's inline style from a div's
            self.inline.append(f"{tag}{{{a['style']}}}")

    def handle_endtag(self, tag):
        if tag == "style" and self._in_style:
            self.styles.append("".join(self._buf))
            self._in_style = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_style:
            self._buf.append(data)
        elif self._in_title and len(self.title) < 200:
            self.title += data


IMPORT_RE = re.compile(r"""@import\s+(?:url\(\s*)?['"]?([^'")\s;]+)""", re.I)


def analyse_site(url):
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    html, final_url, truncated = fetch(url, MAX_HTML, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    page = PageCollector()
    page.feed(html)

    hrefs, seen = [], set()
    for h in page.links:
        absolute = urljoin(final_url, h.strip())
        if absolute not in seen and absolute.startswith(("http://", "https://")):
            seen.add(absolute)
            hrefs.append(absolute)
    skipped = max(0, len(hrefs) - MAX_SHEETS)
    hrefs = hrefs[:MAX_SHEETS]

    def get_sheet(href):
        try:
            text, final, cut = fetch(href, MAX_SHEET, "text/css,*/*;q=0.1")
            return {"href": final, "text": text, "ok": True, "truncated": cut}
        except FetchError as e:
            return {"href": href, "text": "", "ok": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=6) as pool:
        sheets = list(pool.map(get_sheet, hrefs))

    # follow @import one level deep (common with Google Fonts and some themes)
    imports = []
    for sh in sheets:
        for imp in IMPORT_RE.findall(sh["text"])[:5]:
            absolute = urljoin(sh["href"], imp)
            if absolute not in seen and absolute.startswith(("http://", "https://")):
                seen.add(absolute)
                imports.append(absolute)
    if imports:
        with ThreadPoolExecutor(max_workers=6) as pool:
            sheets += list(pool.map(get_sheet, imports[:10]))

    css, total = [], 0
    for i, block in enumerate(page.styles):
        css.append({"source": f"<style> block {i + 1}", "href": final_url, "text": block})
        total += len(block)
    if page.inline:
        css.append({"source": "style attributes", "href": final_url, "text": "\n".join(page.inline)})
    for sh in sheets:
        if sh["ok"] and total + len(sh["text"]) <= MAX_TOTAL_CSS:
            css.append({"source": sh["href"], "href": sh["href"], "text": sh["text"]})
            total += len(sh["text"])

    return {
        "ok": True,
        "url": final_url,
        "title": page.title.strip(),
        "themeColor": page.theme_color,
        "css": css,
        "sheets": [{"href": s["href"], "ok": s["ok"], "error": s.get("error"),
                    "bytes": len(s["text"]), "truncated": s.get("truncated", False)} for s in sheets],
        "skippedSheets": skipped,
        "htmlTruncated": truncated,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PDTableGenerator/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Private-Network", "true")  # lets index.html opened as a file reach the helper
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # CORS / Private Network Access preflight
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("localhost", "127.0.0.1"):  # blocks DNS-rebinding style access
            return self._json(403, {"ok": False, "error": "Forbidden host"})
        path = urlparse(self.path)

        if path.path in ("/", "/index.html"):
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.path == "/api/ping":
            return self._json(200, {"ok": True})

        if path.path == "/api/site-styles":
            origin = self.headers.get("Origin")
            if origin is not None and origin not in ALLOWED_ORIGINS:
                return self._json(403, {"ok": False, "error": "Requests are only accepted from the table generator."})
            url = (parse_qs(path.query).get("url") or [""])[0].strip()
            if not url:
                return self._json(400, {"ok": False, "error": "No URL given."})
            try:
                return self._json(200, analyse_site(url))
            except FetchError as e:
                return self._json(200, {"ok": False, "error": str(e)})
            except Exception as e:  # keep the helper alive whatever a site throws at it
                return self._json(200, {"ok": False, "error": f"Unexpected problem reading that site ({type(e).__name__})."})

        self._json(404, {"ok": False, "error": "Not found"})


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second process bind the same port, so a double launch
    # would silently start a duplicate. Turn it off there so we can detect "already running".
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def main():
    url = f"http://localhost:{PORT}"
    open_browser = "--no-browser" not in sys.argv
    try:
        server = Server(("127.0.0.1", PORT), Handler)
    except OSError:
        # already running (e.g. launched twice): just open the existing one
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=2):
                pass
            print(f"The table generator is already running at {url}. Opening it.")
            if open_browser:
                webbrowser.open(url)
            sys.exit(0)
        except Exception:
            print(f"Port {PORT} is being used by another program, so the table generator can't start.")
            sys.exit(1)
    print(f"HTML Table Generator running at {url}  (Ctrl+C to stop)", flush=True)
    print("Keep this window open while you use it. Closing it stops the helper.", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
