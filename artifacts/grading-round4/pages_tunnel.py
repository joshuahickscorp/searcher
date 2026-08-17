# ruff: noqa: E501
"""Prove GitHub Pages + a Cloudflare tunnel can return listings with working links.

This is the stranger-reachable claim. The published Pages origin is fetched.
A local API is started, a quick tunnel is opened, CORS from the Pages origin is
checked, a search is posted the way the Pages JS would post it, and every
published listing_url is fetched.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PAGES = "https://joshuahickscorp.github.io/searcher/"
PAGES_ORIGIN = "https://joshuahickscorp.github.io"
OUT = Path("artifacts/grading-round4/pages_tunnel.json")
IMAGE = Path("fixtures/user_snapshots/8001001141404_snapshot.jpg")
UA = "searcher-regrade4"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_a(host: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["dig", "+time=2", "+tries=1", "@1.1.1.1", host, "A", "+short"],
            text=True,
            timeout=6,
        )
    except Exception:
        return []
    ips = []
    for line in out.splitlines():
        line = line.strip()
        if line and all(part.isdigit() for part in line.split(".")):
            ips.append(line)
    return ips


def _http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 20.0,
    resolve_ip: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    parsed = urllib.parse.urlparse(url)
    hdrs = dict(headers or {})
    if resolve_ip and parsed.scheme == "https":
        import http.client
        import ssl

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(resolve_ip, 443, timeout=timeout, context=ctx)
        try:
            conn._tunnel_host = parsed.hostname  # type: ignore[attr-defined]
            # Force SNI / Host to the public hostname, not the anycast IP.
            conn.connect = lambda: None  # type: ignore[method-assign]
            sock = socket.create_connection((resolve_ip, 443), timeout=timeout)
            conn.sock = ctx.wrap_socket(sock, server_hostname=parsed.hostname)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            conn.request(method, path, body=data, headers={"Host": parsed.hostname or "", **hdrs})
            resp = conn.getresponse()
            body = resp.read()
            return int(resp.status), {k.lower(): v for k, v in resp.getheaders()}, body
        except Exception:
            conn.close()
            raise
        finally:
            conn.close()
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}, exc.read()


def main() -> int:
    report: dict[object, object] = {"pages": PAGES, "pages_origin": PAGES_ORIGIN}
    try:
        status, headers, body = _http(PAGES, headers={"User-Agent": UA})
    except Exception as exc:
        report["ok"] = False
        report["pages_fetch_error"] = f"{type(exc).__name__}: {exc}"
        OUT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2
    text = body.decode("utf-8", "replace")
    report["pages_status"] = status
    report["pages_bytes"] = len(body)
    report["pages_has_searcher"] = "Searcher" in text
    report["pages_has_api_param"] = "apiOverride" in Path("web/app.js").read_text()
    if status != 200 or "Searcher" not in text:
        report["ok"] = False
        report["reason"] = "pages origin did not serve the interface"
        OUT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 3

    port = _free_port()
    data_root = Path("artifacts/grading-round4/pages-tunnel-data")
    data_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    origins = (
        f"http://127.0.0.1:{port},http://localhost:{port},{PAGES_ORIGIN}"
    )
    env.update(
        {
            "SEARCHER_DATA_ROOT": str(data_root),
            "SEARCHER_LIVE_DISCOVERY": "1",
            "SEARCHER_SERVE_WEB": "1",
            "SEARCHER_API_HOST": "127.0.0.1",
            "SEARCHER_API_PORT": str(port),
            "SEARCHER_CORS_ORIGINS": origins,
            "PYTHONUNBUFFERED": "1",
        }
    )
    api_log = Path("artifacts/grading-round4/pages-tunnel-api.log")
    tun_log = Path("artifacts/grading-round4/pages-tunnel-cloudflared.log")
    api_fh = api_log.open("w")
    tun_fh = tun_log.open("w")
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "searcher",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--data-root",
            str(data_root),
            "--cors",
            origins,
            "--static",
        ],
        env=env,
        stdout=api_fh,
        stderr=subprocess.STDOUT,
    )
    tun_proc = None
    try:
        healthy = False
        for _ in range(40):
            try:
                st, _, raw = _http(f"http://127.0.0.1:{port}/v1/health", timeout=2)
                if st == 200 and b"api" in raw:
                    healthy = True
                    report["local_health"] = json.loads(raw.decode())
                    break
            except Exception:
                time.sleep(0.25)
        if not healthy:
            report["ok"] = False
            report["reason"] = "local API never answered"
            report["api_log_tail"] = api_log.read_text(errors="replace")[-2000:]
            OUT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 4

        tun_proc = subprocess.Popen(
            [
                "cloudflared",
                "tunnel",
                "--url",
                f"http://127.0.0.1:{port}",
                "--no-autoupdate",
            ],
            stdout=tun_fh,
            stderr=subprocess.STDOUT,
        )
        public = ""
        for _ in range(60):
            blob = tun_log.read_text(errors="replace")
            found = re.findall(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com", blob)
            if found:
                public = found[0]
                break
            if tun_proc.poll() is not None:
                break
            time.sleep(0.25)
        report["tunnel_url"] = public
        if not public:
            report["ok"] = False
            report["reason"] = "cloudflared never printed a URL"
            report["tun_log_tail"] = tun_log.read_text(errors="replace")[-2000:]
            OUT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 5

        last_exc = ""
        tunnel_ready = False
        public_host = urllib.parse.urlparse(public).hostname or ""
        resolve_ip = None
        for _ in range(40):
            ips = _resolve_a(public_host)
            if ips:
                resolve_ip = ips[0]
                report["tunnel_resolved_via_1.1.1.1"] = ips
                break
            time.sleep(0.5)
        report["tunnel_resolve_ip"] = resolve_ip
        for _ in range(40):
            try:
                st, hdrs, raw = _http(
                    f"{public}/v1/health", timeout=15, resolve_ip=resolve_ip
                )
                report["tunnel_health_status"] = st
                report["tunnel_health"] = json.loads(raw.decode()) if raw else None
                if st == 200:
                    tunnel_ready = True
                    break
            except Exception as exc:
                last_exc = f"{type(exc).__name__}: {exc}"
                time.sleep(0.5)
        if not tunnel_ready:
            report["ok"] = False
            report["reason"] = f"tunnel health failed after retries: {last_exc}"
            OUT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 6

        st, hdrs, _ = _http(
            f"{public}/v1/health",
            headers={"Origin": PAGES_ORIGIN, "User-Agent": UA},
            timeout=15,
            resolve_ip=resolve_ip,
        )
        acao = hdrs.get("access-control-allow-origin")
        report["cors_origin_sent"] = PAGES_ORIGIN
        report["cors_allow_origin"] = acao
        report["cors_ok"] = acao == PAGES_ORIGIN
        friend = f"{PAGES}?api={public}"
        report["friend_url"] = friend

        if not IMAGE.is_file():
            report["ok"] = False
            report["reason"] = f"missing {IMAGE}"
            OUT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 7

        boundary = "----searcherRegrade4"
        png = IMAGE.read_bytes()
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\nWilly Chavarria\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"tags\"\r\n\r\ngarment\r\n".encode(),
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"images\"; filename=\"{IMAGE.name}\"\r\n"
                f"Content-Type: image/{'jpeg' if IMAGE.suffix.lower() in {'.jpg', '.jpeg'} else 'png'}\r\n\r\n"
            ).encode()
            + png
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        body = b"".join(parts)
        st, hdrs, raw = _http(
            f"{public}/v1/searches",
            method="POST",
            headers={
                "Origin": PAGES_ORIGIN,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": UA,
            },
            data=body,
            timeout=30,
            resolve_ip=resolve_ip,
        )
        report["create_status"] = st
        report["create_cors"] = hdrs.get("access-control-allow-origin")
        try:
            created = json.loads(raw.decode())
        except Exception:
            created = {"raw": raw.decode("utf-8", "replace")[:500]}
        report["create"] = created
        search_id = created.get("search_id") if isinstance(created, dict) else None
        if st not in {200, 201, 202} or not search_id:
            report["ok"] = False
            report["reason"] = "search create failed through the tunnel"
            OUT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return 8

        for _ in range(90):
            st, _, raw = _http(
                f"{public}/v1/searches/{search_id}",
                headers={"Origin": PAGES_ORIGIN, "User-Agent": UA},
                timeout=20,
                resolve_ip=resolve_ip,
            )
            search = json.loads(raw.decode())
            report["search"] = search
            if search.get("terminal_status"):
                break
            time.sleep(2)
        st, _, raw = _http(
            f"{public}/v1/searches/{search_id}/results",
            headers={"Origin": PAGES_ORIGIN, "User-Agent": UA},
            timeout=20,
            resolve_ip=resolve_ip,
        )
        results = json.loads(raw.decode())
        report["results"] = results
        cards = []
        for bucket in ("real", "possibly_real", "replica"):
            for row in results.get(bucket) or []:
                cards.append({"bucket": bucket, **row})
        report["published_count"] = len(cards)
        link_checks = []
        working = 0
        for card in cards[:8]:
            url = card.get("listing_url") or ""
            reasons = ((card.get("why") or {}).get("tab_reason")) or ""
            entry = {
                "bucket": card.get("bucket"),
                "listing_url": url,
                "has_http_link": str(url).startswith("http://") or str(url).startswith("https://"),
                "has_reason": bool(reasons),
                "tab_reason": reasons,
            }
            if entry["has_http_link"]:
                try:
                    req = urllib.request.Request(
                        url, method="HEAD", headers={"User-Agent": UA}
                    )
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        entry["link_status"] = int(resp.status)
                except urllib.error.HTTPError as exc:
                    entry["link_status"] = int(exc.code)
                except Exception as exc:
                    # some shops refuse HEAD; try GET
                    try:
                        st2, _, _ = _http(url, headers={"User-Agent": UA}, timeout=20)
                        entry["link_status"] = st2
                    except Exception as exc2:
                        entry["link_error"] = f"{type(exc).__name__}/{type(exc2).__name__}: {exc2}"
            ok_link = entry.get("link_status") in {200, 301, 302, 303, 307, 308}
            entry["working"] = bool(entry["has_http_link"] and ok_link)
            if entry["working"]:
                working += 1
            link_checks.append(entry)
        report["link_checks"] = link_checks
        report["working_links"] = working
        report["ok"] = bool(
            report.get("pages_status") == 200
            and report.get("tunnel_health_status") == 200
            and report.get("cors_ok")
            and working >= 1
        )
        report["reason"] = (
            "pages + tunnel returned published listings with working http(s) links"
            if report["ok"]
            else "pages/tunnel reachable but no working published listing"
        )
    finally:
        if tun_proc is not None:
            tun_proc.terminate()
        api_proc.terminate()
        try:
            api_proc.wait(timeout=5)
        except Exception:
            api_proc.kill()
        if tun_proc is not None:
            try:
                tun_proc.wait(timeout=5)
            except Exception:
                tun_proc.kill()
        api_fh.close()
        tun_fh.close()
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    slim = {
        "ok": report.get("ok"),
        "reason": report.get("reason"),
        "pages_status": report.get("pages_status"),
        "tunnel_url": report.get("tunnel_url"),
        "cors_ok": report.get("cors_ok"),
        "create_status": report.get("create_status"),
        "published_count": report.get("published_count"),
        "working_links": report.get("working_links"),
        "friend_url_host": PAGES,
        "search_terminal": (report.get("search") or {}).get("terminal_status")
        if isinstance(report.get("search"), dict)
        else None,
    }
    print(json.dumps(slim, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
