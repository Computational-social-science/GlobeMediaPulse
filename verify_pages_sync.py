import hashlib
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


PAGES_URL = (os.getenv("PAGES_URL", "https://computational-social-science.github.io/GlobeMediaPulse/") or "").strip()
DIST_DIR = Path(os.getenv("DIST_DIR", "frontend/dist"))
VERIFY_REMOTE = (os.getenv("VERIFY_REMOTE", "1") or "1").strip().lower() in ("1", "true", "yes", "on")
VERIFY_TIMEOUT_S = float(os.getenv("VERIFY_TIMEOUT_S", "10") or "10")
VERIFY_MAX_RETRIES = int(os.getenv("VERIFY_MAX_RETRIES", "8") or "8")
VERIFY_RETRY_DELAY_S = float(os.getenv("VERIFY_RETRY_DELAY_S", "10") or "10")


def _fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "gmp-sync-verify"})
    with urlopen(req, timeout=VERIFY_TIMEOUT_S) as resp:
        return resp.read()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return _sha256_bytes(handle.read())


def _normalize_html(html: str) -> str:
    compact = re.sub(r">\s+<", "><", html)
    return compact.strip()


def _normalize_attr_value(key: str, value: str) -> str:
    if value is None:
        return ""
    if key == "class":
        return " ".join(sorted(v for v in value.split() if v))
    return value.strip()


STRUCT_ATTRS = {
    "id",
    "class",
    "role",
    "name",
    "type",
    "aria-label",
    "aria-hidden",
    "aria-expanded",
}


class HtmlSnapshot(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[tuple[str, str, tuple[tuple[str, str], ...]]] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs, is_end=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs, is_end=False)
        self.tokens.append(("end", tag, ()))

    def handle_endtag(self, tag: str) -> None:
        self.tokens.append(("end", tag, ()))

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]], is_end: bool) -> None:
        attr_map = {k: v for k, v in attrs}
        filtered: list[tuple[str, str]] = []
        for key, value in attr_map.items():
            if key in STRUCT_ATTRS:
                normalized = _normalize_attr_value(key, value or "")
                if normalized:
                    filtered.append((key, normalized))
        filtered.sort()
        self.tokens.append(("start", tag, tuple(filtered)))
        self._collect_asset(tag, attr_map)

    def _collect_asset(self, tag: str, attr_map: dict[str, str | None]) -> None:
        target = None
        if tag == "script":
            target = attr_map.get("src")
        elif tag in ("img", "source"):
            target = attr_map.get("src")
        elif tag == "link":
            target = attr_map.get("href")
        if not target:
            return
        if target.startswith("http://") or target.startswith("https://") or target.startswith("data:"):
            return
        parsed = urlparse(target)
        if parsed.scheme or parsed.netloc:
            return
        path = parsed.path or ""
        if path.startswith("./"):
            path = path[2:]
        if path.startswith("/"):
            path = path[1:]
        if not path:
            return
        self.assets.append(path)


def _load_snapshot_from_html(html: str) -> HtmlSnapshot:
    parser = HtmlSnapshot()
    parser.feed(html)
    return parser


def _ensure_dist_dir() -> None:
    if not DIST_DIR.exists():
        raise SystemExit(f"dist directory missing: {DIST_DIR}")
    if not (DIST_DIR / "index.html").exists():
        raise SystemExit(f"index.html missing in dist: {DIST_DIR / 'index.html'}")


def _compare_html(local_html: str, remote_html: str) -> None:
    local_snapshot = _load_snapshot_from_html(local_html)
    remote_snapshot = _load_snapshot_from_html(remote_html)
    if local_snapshot.tokens != remote_snapshot.tokens:
        raise SystemExit("HTML structure mismatch")
    if _normalize_html(local_html) != _normalize_html(remote_html):
        raise SystemExit("HTML content mismatch")


def _verify_assets(local_snapshot: HtmlSnapshot, base_url: str, verify_remote: bool) -> None:
    unique_assets = sorted(set(local_snapshot.assets))
    if not unique_assets:
        raise SystemExit("no assets detected in index.html")
    for asset in unique_assets:
        local_path = DIST_DIR / asset
        if not local_path.exists():
            raise SystemExit(f"local asset missing: {asset}")
        local_hash = _sha256_file(local_path)
        if verify_remote:
            remote_url = urljoin(base_url, asset)
            remote_hash = _sha256_bytes(_fetch_bytes(remote_url))
            if local_hash != remote_hash:
                raise SystemExit(f"asset mismatch: {asset}")


def _fetch_remote_index(base_url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, VERIFY_MAX_RETRIES + 1):
        try:
            data = _fetch_bytes(base_url)
            return data.decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < VERIFY_MAX_RETRIES:
                time.sleep(VERIFY_RETRY_DELAY_S)
    raise SystemExit(f"failed to fetch remote index: {last_error}")


def main() -> None:
    if not PAGES_URL:
        raise SystemExit("PAGES_URL is required")
    base_url = PAGES_URL if PAGES_URL.endswith("/") else PAGES_URL + "/"
    _ensure_dist_dir()
    local_html = (DIST_DIR / "index.html").read_text(encoding="utf-8", errors="replace")
    local_snapshot = _load_snapshot_from_html(local_html)
    if VERIFY_REMOTE:
        remote_html = _fetch_remote_index(base_url)
        _compare_html(local_html, remote_html)
        _verify_assets(local_snapshot, base_url, True)
    else:
        _verify_assets(local_snapshot, base_url, False)
    print("Pages sync verification passed.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        print(str(exc))
        sys.exit(1)
