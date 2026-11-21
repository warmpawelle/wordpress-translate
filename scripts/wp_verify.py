#!/usr/bin/env python3
"""Verify a translated WordPress page set against its source pages.

Checks, per URL: HTTP status, <html lang>, link set, media set, block count,
language-switcher coverage, residual English ratio. Read-only.

Usage:
    python wp_verify.py --base-url https://example.com --lang es --paths /,/about/,/blog/
    python wp_verify.py --base-url https://example.com --lang es --from-sitemap
    python wp_verify.py --base-url https://example.com --lang es --sample 3 --json out.json

Exit code 0 = all checks passed, 1 = at least one failure.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

UA = "Mozilla/5.0 (compatible; wp-verify/1.0)"
TIMEOUT = 30
IGNORED_PARAMS = {"_wpnonce", "ver", "nocache", "preview", "fbclid", "gclid", "_gl"}
SKIP_TAGS = {"script", "style", "code", "pre", "noscript"}

EN_STOPWORDS = {
    "the", "and", "with", "your", "from", "this", "that", "for", "you", "our",
    "are", "was", "were", "will", "can", "have", "has", "not", "but", "all",
    "how", "what", "when", "where", "which", "they", "them", "their", "his",
    "her", "its", "about", "into", "more", "than", "then", "there", "here",
    "also", "just", "only", "over", "under", "after", "before", "between",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.hreflangs = []
        self.hrefs = []
        self.media = []
        self.text = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in SKIP_TAGS:
            self._skip += 1
            return
        if tag == "html" and attrs.get("lang"):
            self.lang = attrs["lang"]
        if tag == "link" and attrs.get("hreflang"):
            self.hreflangs.append(attrs["hreflang"])
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag == "img":
            if attrs.get("src"):
                self.media.append(attrs["src"])
            if attrs.get("srcset"):
                for part in attrs["srcset"].split(","):
                    url = part.strip().split(" ")[0]
                    if url:
                        self.media.append(url)
        if tag == "source" and attrs.get("srcset"):
            for part in attrs["srcset"].split(","):
                url = part.strip().split(" ")[0]
                if url:
                    self.media.append(url)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            chunk = data.strip()
            if chunk:
                self.text.append(chunk)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), resp.read(1500000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def norm_url(raw, page_url, lang):
    if not raw or raw.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    absolute = urljoin(page_url, raw)
    parsed = urlparse(absolute)
    path = parsed.path or "/"
    path = re.sub(r"^/%s(?=/|$)" % re.escape(lang), "", path) or "/"
    path = path.rstrip("/") or "/"
    params = [(k, v) for k, v in parse_qsl(parsed.query) if k not in IGNORED_PARAMS]
    return path + ("?" + urlencode(params) if params else "")


def media_names(items, page_url):
    names = set()
    for raw in items:
        if not raw:
            continue
        path = urlparse(urljoin(page_url, raw)).path
        if path:
            names.add(path.rsplit("/", 1)[-1])
    return names


def english_ratio(texts):
    words = []
    for chunk in texts:
        words.extend(re.findall(r"[A-Za-z][A-Za-z'-]{1,}", chunk))
    if not words:
        return 0.0, 0
    hits = sum(1 for w in words if w.lower() in EN_STOPWORDS)
    return hits / float(len(words)), len(words)


def leftover_tokens(texts):
    pattern = re.compile(r"(__[A-Z0-9_]{2,}__|\{\{[^}]{1,40}\}\}|translation missing)")
    return [m.group(0) for chunk in texts for m in pattern.finditer(chunk)][:10]


def load_paths_from_sitemap(base):
    for path in ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml"):
        code, body = fetch(urljoin(base, path))
        if code != 200 or "<loc>" not in body:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
        if locs and locs[0].endswith(".xml"):
            nested = []
            for sub in locs[:5]:
                sub_code, sub_body = fetch(sub)
                if sub_code == 200:
                    nested.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub_body))
            locs = nested or locs
        paths = []
        for loc in locs:
            parsed = urlparse(loc)
            if parsed.netloc and parsed.netloc not in urlparse(base).netloc:
                continue
            if parsed.path.endswith(".xml") or "/wp-" in parsed.path:
                continue
            paths.append(parsed.path or "/")
        if paths:
            return sorted(set(paths))
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lang", required=True, help="target language code, e.g. es")
    parser.add_argument("--paths", help="comma separated paths, e.g. /,/about/,/blog/")
    parser.add_argument("--from-sitemap", action="store_true")
    parser.add_argument("--sample", type=int, default=0, help="randomly keep N paths")
    parser.add_argument("--max-english", type=float, default=0.02)
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    lang = args.lang.strip("/")

    if args.paths:
        paths = [p.strip() or "/" for p in args.paths.split(",")]
    elif args.from_sitemap:
        paths = load_paths_from_sitemap(base)
    else:
        parser.error("need --paths or --from-sitemap")

    if not paths:
        print("no paths to check")
        return 1

    mangled = [p for p in paths if re.match(r"^[A-Za-z]:[\\/]", p)]
    if mangled:
        print("path was rewritten by the shell: %s" % mangled[:2])
        print("rerun with MSYS_NO_PATHCONV=1, or pass paths without the leading slash")
        return 1
    if args.sample and len(paths) > args.sample:
        step = max(1, len(paths) // args.sample)
        paths = paths[::step][: args.sample]

    results = []
    failures = 0

    print("")
    print("verifying %d path(s) against /%s/" % (len(paths), lang))
    print("-" * 96)
    print("%-34s %-11s %-9s %-8s %-8s %-7s %s" % ("path", "code", "lang", "links", "media", "en%", "verdict"))

    for path in paths:
        src_url = base + (path if path.startswith("/") else "/" + path)
        tgt_url = base + "/" + lang + (path if path.startswith("/") else "/" + path)

        src_code, src_html = fetch(src_url)
        tgt_code, tgt_html = fetch(tgt_url)

        row = {"path": path, "source_code": src_code, "target_code": tgt_code, "problems": []}

        if tgt_code != 200:
            row["problems"].append("target HTTP %s" % tgt_code)
        if src_code != 200:
            row["problems"].append("source HTTP %s" % src_code)

        src = PageParser()
        tgt = PageParser()
        if src_html:
            src.feed(src_html)
        if tgt_html:
            tgt.feed(tgt_html)

        # html lang
        if tgt.lang and not tgt.lang.lower().startswith(lang.lower()):
            row["problems"].append("html lang=%s" % tgt.lang)
        elif not tgt.lang:
            row["problems"].append("no html lang")

        # links
        src_links = {u for u in (norm_url(h, src_url, lang) for h in src.hrefs) if u}
        tgt_links = {u for u in (norm_url(h, tgt_url, lang) for h in tgt.hrefs) if u}
        link_diff = sorted(tgt_links - src_links)[:5]
        missing_links = sorted(src_links - tgt_links)[:5]
        row["extra_links"] = link_diff
        row["missing_links"] = missing_links

        # media
        src_media = media_names(src.media, src_url)
        tgt_media = media_names(tgt.media, tgt_url)
        media_diff = sorted(tgt_media - src_media)[:5]
        row["extra_media"] = media_diff

        # blocks
        src_blocks = len(re.findall(r"<!--\s*wp:", src_html))
        tgt_blocks = len(re.findall(r"<!--\s*wp:", tgt_html))
        row["blocks"] = [src_blocks, tgt_blocks]
        if src_blocks and src_blocks != tgt_blocks:
            row["problems"].append("blocks %d vs %d" % (src_blocks, tgt_blocks))

        # residual english
        ratio, word_count = english_ratio(tgt.text)
        row["english_ratio"] = round(ratio, 4)
        row["words"] = word_count
        if ratio > args.max_english and word_count > 60:
            row["problems"].append("english %.1f%%" % (ratio * 100))

        tokens = leftover_tokens(tgt.text)
        if tokens:
            row["problems"].append("leftover tokens %s" % tokens[:3])

        # switcher: distinct language prefixes among outbound links
        prefixes = set()
        for href in tgt.hrefs:
            match = re.match(r"^(?:https?://[^/]+)?/([a-z]{2}(?:-[a-z]{2})?)/", href)
            if match:
                prefixes.add(match.group(1))
        row["switcher_langs"] = sorted(prefixes)
        if not prefixes:
            row["problems"].append("no language switcher links")

        verdict = "ok" if not row["problems"] else "FAIL"
        if row["problems"]:
            failures += 1
        row["verdict"] = verdict
        results.append(row)

        print("%-34s %-11s %-9s %-8s %-8s %-7s %s" % (
            path[:34],
            "%s>%s" % (src_code, tgt_code),
            (tgt.lang or "-")[:9],
            "%d/%d" % (len(tgt_links), len(src_links)),
            "%d/%d" % (len(tgt_media), len(src_media)),
            "%.1f" % (ratio * 100),
            verdict,
        ))
        for problem in row["problems"]:
            print("      ! %s" % problem)
        if row["problems"]:
            for extra in link_diff[:3]:
                print("      + link only in translation: %s" % extra)

    print("-" * 96)
    total = len(results)
    print("%d/%d passed" % (total - failures, total))
    print("")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump({"base": base, "lang": lang, "results": results}, handle, ensure_ascii=False, indent=2)
        print("written: %s" % args.json_out)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
