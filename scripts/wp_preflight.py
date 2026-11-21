#!/usr/bin/env python3
"""Read-only preflight for a WordPress site before adding /es/ style languages.

Collects what the site actually is: WP version hints, active theme, plugin
slugs, post types, permalink shape, sitemap size, multilingual plugin state,
cache layer. Writes nothing.

Usage:
    python wp_preflight.py --base-url https://example.com
    python wp_preflight.py --base-url https://example.com --json preflight.json
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (compatible; wp-preflight/1.0; +https://example.com)"
TIMEOUT = 25

MULTILINGUAL_MARKERS = {
    "polylang": ["polylang", "pll_"],
    "wpml": ["sitepress", "wpml", "icl_"],
    "translatepress": ["translatepress", "trp_"],
    "weglot": ["weglot"],
    "qtranslate": ["qtranslate"],
}


def site(base, path):
    """Join without urljoin: urljoin would drop a subdirectory install (/news)."""
    return base.rstrip("/") + (path if path.startswith("/") else "/" + path)


def fetch(url, accept="text/html,application/json"):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(3000000).decode("utf-8", "ignore")
            return resp.getcode(), dict(resp.headers), body
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), ""
    except Exception as exc:  # noqa: BLE001 - network shapes vary wildly
        return 0, {}, "%s: %s" % (type(exc).__name__, exc)


def get_json(base, path):
    code, _, body = fetch(site(base, path), accept="application/json")
    if code != 200 or not body:
        return code, None
    try:
        return code, json.loads(body)
    except ValueError:
        return code, None


def count_type(base, rest_base):
    """Return (total, sample_link) using the X-WP-Total header."""
    url = "%s/wp-json/wp/v2/%s?per_page=1&_fields=id,link" % (base, rest_base)
    code, headers, body = fetch(url, accept="application/json")
    if code != 200:
        return None, None
    total = headers.get("X-WP-Total") or headers.get("x-wp-total")
    link = None
    try:
        data = json.loads(body)
        if data:
            link = data[0].get("link")
    except ValueError:
        pass
    return (int(total) if total else None), link


def detect_sitemap(base, html):
    candidates = []
    robots = fetch(site(base, "/robots.txt"))[2]
    for line in robots.splitlines():
        if line.lower().startswith("sitemap:"):
            candidates.append(line.split(":", 1)[1].strip())
    for path in ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml"):
        candidates.append(site(base, path))

    seen = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        code, _, body = fetch(url)
        if code == 200 and "<loc>" in body:
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
            return {"url": url, "loc_count": len(locs), "sample": locs[:3]}
    return {"url": None, "loc_count": 0, "sample": []}


def fingerprint(html):
    generator = re.search(r'<meta[^>]+name="generator"[^>]+content="([^"]+)"', html, re.I)
    themes = sorted(set(re.findall(r"/wp-content/themes/([a-zA-Z0-9._-]+)/", html)))
    plugins = sorted(set(re.findall(r"/wp-content/plugins/([a-zA-Z0-9._-]+)/", html)))
    lang = re.search(r"<html[^>]+lang=[\"']([^\"']+)", html, re.I)
    hreflangs = sorted(set(re.findall(r'hreflang=["\']([^"\']+)["\']', html, re.I)))
    return {
        "generator": generator.group(1) if generator else None,
        "themes": themes,
        "plugins": plugins,
        "html_lang": lang.group(1) if lang else None,
        "hreflangs": hreflangs,
    }


def detect_multilingual(namespaces, plugins, html):
    found = {}
    blob = " ".join(namespaces).lower() + " " + " ".join(plugins).lower() + " " + html.lower()
    for name, markers in MULTILINGUAL_MARKERS.items():
        hits = [m for m in markers if m in blob]
        if hits:
            found[name] = hits
    return found


def permalink_shape(link):
    if not link:
        return "unknown"
    path = urlparse(link).path
    if re.search(r"[?&]p=\d+", link):
        return "plain (?p=ID)"
    if path.endswith("/") and path.count("/") >= 2:
        return "pretty (/%postname%/)"
    return "unknown (" + path + ")"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    report = {"base_url": base, "checks": {}, "warnings": [], "ok": []}

    # --- REST root -------------------------------------------------------
    code, root = get_json(base, "/wp-json/")
    report["checks"]["rest_root_status"] = code
    if code != 200 or not root:
        report["warnings"].append(
            "REST root not reachable (HTTP %s). Use WP-CLI for discovery." % code
        )
        root = {}
    else:
        report["site"] = {
            "name": root.get("name"),
            "description": root.get("description"),
            "home": root.get("home"),
            "url": root.get("url"),
            "gmt_offset": root.get("gmt_offset"),
            "namespaces": root.get("namespaces", []),
        }
        report["ok"].append("REST root reachable")

    namespaces = report.get("site", {}).get("namespaces", [])

    # --- post types ------------------------------------------------------
    _, types = get_json(base, "/wp-json/wp/v2/types")
    post_types = {}
    if types:
        for key, val in types.items():
            if key in ("attachment", "nav_menu_item", "wp_block", "wp_template"):
                continue
            if key.startswith("wp_"):
                continue
            post_types[key] = {
                "name": val.get("name"),
                "rest_base": val.get("rest_base") or key,
            }
    report["checks"]["post_types"] = post_types

    counts = {}
    sample_link = None
    for key, val in post_types.items():
        total, link = count_type(base, val["rest_base"])
        counts[key] = total
        if link and not sample_link and key in ("page", "post"):
            sample_link = link
    counts = {k: v for k, v in counts.items() if v is not None}
    report["checks"]["counts"] = counts
    report["checks"]["permalink_shape"] = permalink_shape(sample_link)

    # --- front page + fingerprint ---------------------------------------
    fcode, fheaders, html = fetch(site(base, "/"))
    report["checks"]["home_status"] = fcode
    fp = fingerprint(html) if html and fcode == 200 else {}
    report["checks"]["fingerprint"] = fp

    cache_headers = {
        k.lower(): v
        for k, v in (fheaders or {}).items()
        if k.lower() in ("x-cache", "cf-cache-status", "x-litespeed-cache", "x-cache-enabled", "server", "via")
    }
    report["checks"]["cache_headers"] = cache_headers

    # --- sitemap ---------------------------------------------------------
    report["checks"]["sitemap"] = detect_sitemap(base, html)

    # --- multilingual state ---------------------------------------------
    ml = detect_multilingual(namespaces, fp.get("plugins", []), html)
    report["checks"]["multilingual_detected"] = ml
    report["checks"]["hreflangs_on_home"] = fp.get("hreflangs", [])

    # --- target prefix collision ----------------------------------------
    prefix_code = fetch(site(base, "/es/"))[0]
    report["checks"]["/es/ status"] = prefix_code
    if prefix_code == 200:
        report["warnings"].append(
            "/es/ already returns 200. Either Spanish content exists already, "
            "or the server rewrites everything to the home page. Inspect before adding languages."
        )

    if counts.get("product"):
        report["ok"].append("WooCommerce-style product post type present (%s items)" % counts["product"])
    if fp.get("plugins"):
        report["ok"].append("plugin slugs visible in HTML: %d" % len(fp["plugins"]))
    if report["checks"]["sitemap"]["url"]:
        report["ok"].append("sitemap found: %s" % report["checks"]["sitemap"]["url"])
    else:
        report["warnings"].append("No sitemap found. Build the URL list from the REST API or WP-CLI.")

    if not fp.get("themes"):
        report["warnings"].append(
            "No theme slug in HTML (asset optimisation may strip paths). Read it with `wp theme list`."
        )

    # --- human summary ---------------------------------------------------
    print("")
    print("WP preflight: %s" % base)
    print("=" * 64)
    print("REST root        : HTTP %s" % code)
    if report.get("site"):
        print("Site name        : %s" % report["site"].get("name"))
        print("Home URL         : %s" % report["site"].get("home"))
        print("Generator        : %s" % (fp.get("generator") or "n/a"))
        print("HTML lang        : %s" % (fp.get("html_lang") or "n/a"))
        print("Theme            : %s" % (", ".join(fp.get("themes") or []) or "unknown"))
        print("Plugins in HTML  : %s" % (", ".join(fp.get("plugins") or []) or "none visible"))
        print("Permalinks       : %s" % report["checks"]["permalink_shape"])
        print("Post types       : %s" % json.dumps(counts, ensure_ascii=True))
        print("Sitemap          : %s (%d locs)" % (
            report["checks"]["sitemap"]["url"] or "not found",
            report["checks"]["sitemap"]["loc_count"],
        ))
        print("Multilingual     : %s" % (json.dumps(ml) if ml else "none detected"))
        print("hreflang on home : %s" % (", ".join(fp.get("hreflangs") or []) or "none"))
        print("/es/ status      : HTTP %s" % prefix_code)
        print("Cache headers    : %s" % (json.dumps(cache_headers) if cache_headers else "none"))
    print("-" * 64)
    for line in report["ok"]:
        print("  [OK]   %s" % line)
    for line in report["warnings"]:
        print("  [WARN] %s" % line)
    print("")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print("written: %s" % args.json_out)

    return 0 if code == 200 else 2


if __name__ == "__main__":
    sys.exit(main())
