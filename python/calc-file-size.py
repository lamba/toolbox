#!/usr/bin/env python3
import sys, os
from email import policy
from email.parser import BytesParser

GMAIL_CLIP_BYTES = 102 * 1024  # ~102 KB

def read_html_bytes(path: str) -> bytes:
    raw = open(path, "rb").read()
    # If it looks like raw HTML, just return it as-is
    sniff = raw.lstrip()[:20].lower()
    if sniff.startswith(b'<!doctype') or sniff.startswith(b'<html'):
        return raw
    # Otherwise parse as an .eml (full raw source)
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            # policy=default -> get_content() returns str (decoded by charset)
            html_str = part.get_content()
            charset = part.get_content_charset() or "utf-8"
            return html_str.encode(charset, errors="replace")
    raise RuntimeError("No text/html part found in file.")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 calc-file-size.py <path-to-.eml-or-.html>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    html_bytes = read_html_bytes(path)
    n = len(html_bytes)
    print(f"Decoded HTML bytes: {n}  (~{n/1024:.1f} KB)")
    if n > GMAIL_CLIP_BYTES:
        over = n - GMAIL_CLIP_BYTES
        print(f"⚠️ Over Gmail’s ~102 KB clip limit by {over} bytes (~{over/1024:.1f} KB).")
        # Give a small safety buffer
        target = n - (over + 2048)
        print("Tip: trim at least ~2 KB more than the overage to be safe.")
    else:
        spare = GMAIL_CLIP_BYTES - n
        print(f"✅ Under the limit by {spare} bytes (~{spare/1024:.1f} KB).")

if __name__ == "__main__":
    main()
