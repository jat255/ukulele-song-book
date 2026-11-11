"""Render the shared web music blocks using a controlled Chromium instance."""

import hashlib
import os
import socket
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from .models import PdfArtifact, PdfRenderRequest

ROOT = Path(__file__).resolve().parents[3]


def render_pdf(request: PdfRenderRequest) -> PdfArtifact:
    if request.snapshots:
        if len(request.snapshots) != 1:
            raise ValueError("Only one snapshot is supported during feasibility")
        request = replace(request, source=request.snapshots[0].source, snapshots=[])
    if request.settings is not None:
        settings = request.settings
        request = replace(
            request,
            paper=settings.paper,
            font_pt=settings.font_pt,
            columns=settings.columns,
            margins_mm=settings.margins_mm,
            density=settings.density,
            diagrams=settings.diagrams,
            settings=None,
        )
    if request.columns == "auto":
        candidates = []
        for columns in (1, 2):
            try:
                candidates.append(render_pdf(replace(request, columns=columns)))
            except ValueError as exc:
                if "exceeds available column width" not in str(exc):
                    raise
        if not candidates:
            raise ValueError("Music exceeds available column width")
        return min(
            candidates,
            key=lambda candidate: (
                candidate.page_count,
                candidate.wraps,
                candidate.columns,
            ),
        )
    if (
        request.paper not in {"Letter", "A4"}
        or request.columns not in {1, 2}
        or not 6 <= request.font_pt <= 72
        or not 0 <= request.margins_mm <= 40
        or request.density not in {"tight", "compact", "relaxed"}
        or not -24 <= request.performance.semitones <= 24
        or not 0 <= request.performance.capo <= 12
        or request.performance.spelling not in {"auto", "sharps", "flats"}
        or request.performance.tuning not in {"high-g", "low-g"}
    ):
        raise ValueError("Invalid print settings")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            "npm",
            "run",
            "dev",
            "--workspace",
            "@songbook/web",
            "--",
            "--port",
            str(port),
            "--strictPort",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.environ.get("SONGBOOK_RENDER_INHERIT_GROUP") != "1",
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(url, timeout=1):
                    break
            except (OSError, URLError):
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Local renderer failed to start")
                time.sleep(0.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            browser_version = browser.version
            try:
                width_mm = 215.9 if request.paper == "Letter" else 210
                usable_width = int((width_mm - 2 * request.margins_mm) * 96 / 25.4)
                page = browser.new_page(
                    viewport={"width": usable_width, "height": 1056}
                )
                page.route(
                    "**/*",
                    lambda route: (
                        route.continue_()
                        if route.request.url.startswith(url + "/")
                        else route.abort()
                    ),
                )
                page.goto(url + "/?feasibility", wait_until="networkidle")
                page.wait_for_function("typeof window.renderSong === 'function'")
                page.evaluate(
                    'args => window.renderSong(args.source, "print", args.font, args.columns, args.performance, args.density, args.diagrams)',
                    {
                        "source": request.source,
                        "font": request.font_pt,
                        "columns": request.columns,
                        "performance": {
                            "semitones": request.performance.semitones,
                            "spelling": request.performance.spelling,
                            "capo": request.performance.capo,
                            "tuning": request.performance.tuning,
                        },
                        "density": request.density,
                        "diagrams": request.diagrams,
                    },
                )
                page.wait_for_function(
                    "document.documentElement.dataset.renderReady === 'true'"
                )
                page.emulate_media(media="print")
                page.add_style_tag(
                    content=f"@page {{ size: {request.paper}; margin: {request.margins_mm}mm; }}"
                )
                page_height_mm = 279.4 if request.paper == "Letter" else 297
                usable_height = (page_height_mm - 2 * request.margins_mm) * 96 / 25.4
                too_tall = page.locator(".tab").evaluate_all(
                    "(nodes, limit) => nodes.some(node => node.getBoundingClientRect().height > limit + 1)",
                    usable_height,
                )
                if too_tall:
                    raise ValueError("Tab exceeds available page height")
                oversized = page.locator(".tab").evaluate_all(
                    "(nodes) => nodes.some(n => n.scrollWidth > n.clientWidth + 1)"
                )
                if oversized:
                    raise ValueError("Tab exceeds available column width")
                oversized_lyric = page.locator(".segment").evaluate_all(
                    "(nodes) => nodes.some(n => n.getBoundingClientRect().width > (n.closest('.music').getBoundingClientRect().width - (Number(getComputedStyle(n.closest('.music')).columnCount)-1)*parseFloat(getComputedStyle(n.closest('.music')).columnGap || 0)) / Number(getComputedStyle(n.closest('.music')).columnCount) + 1)"
                )
                oversized_fragment = page.locator(".lyric-fragment").evaluate_all("""nodes => nodes.some(n => {
                    const parent=n.closest('.music'); const css=getComputedStyle(parent);
                    const count=Number(css.columnCount); const width=(parent.getBoundingClientRect().width-(count-1)*parseFloat(css.columnGap || 0))/count;
                    const range=document.createRange(); range.selectNodeContents(n);
                    return Array.from(range.getClientRects()).some(rect => rect.width > width + 1);
                })""")
                if oversized_lyric or oversized_fragment:
                    raise ValueError("Lyric exceeds available column width")
                wraps = page.locator(".lyric-line").evaluate_all("""nodes => nodes.reduce((total,node) => {
                    const range=document.createRange(); range.selectNodeContents(node);
                    const tops=new Set(Array.from(range.getClientRects()).filter(rect => rect.width > 0).map(rect => Math.round(rect.top)));
                    return total + Math.max(0,tops.size-2);
                },0)""")
                pdf = page.pdf(
                    prefer_css_page_size=True, scale=1, print_background=True
                )
            finally:
                browser.close()
        request.output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(pdf).hexdigest()
        path = request.output_dir / (digest + ".pdf")
        path.write_bytes(pdf)
        count = len(PdfReader(path).pages)
        font_dir = ROOT / "apps/web/public/fonts"
        font_hashes = {
            font.name: hashlib.sha256(font.read_bytes()).hexdigest()
            for font in sorted(font_dir.glob("*.ttf"))
        }
        return PdfArtifact(
            path,
            digest,
            count,
            request.columns,
            browser_version=browser_version,
            font_hashes=font_hashes,
            wraps=wraps,
        )
    finally:
        if os.environ.get("SONGBOOK_RENDER_INHERIT_GROUP") == "1":
            server.terminate()
        else:
            os.killpg(server.pid, 15)
        server.wait(timeout=5)
