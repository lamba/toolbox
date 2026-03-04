"""
usage examples:

Same line, any order, whole words (case-insensitive):
    python3 multiline-grep.py --root "/Users/lamba/Dropbox/my-docs/md-notes" --words compar ajo target --same-line

Same line but allow substrings (so “Comparing” matches “compar”):
    python3 multiline-grep.py --root "/Users/lamba/Dropbox/my-docs/md-notes" --words compar ajo target --same-line --substring

Original cross-line behavior (no new switch):
    python3 multiline-grep.py --root "/Users/lamba/Dropbox" --words --cross-line ajo compar

To search across pdfs
    python3 multiline-grep.py --root "/Users/lamba/Dropbox/my-docs/md-notes" --words compar ajo --same-line --substring --pdf --pdf-pages 5 --pdf-timeout 10

"""

import os, re, subprocess, shutil, argparse, logging

logging.getLogger("pdfminer").setLevel(logging.WARNING)

def extract_text_from_pdf(path, timeout=15, max_pages=None, engine_order=("pdftotext","pypdf2","pdfminer")):
    """
    Return extracted text or "".
    Tries engines in order. Each step is wrapped to avoid hangs.
    """
    engines = tuple(e.lower() for e in engine_order)

    # 1) pdftotext (Poppler) — fastest/most robust if installed
    if "pdftotext" in engines and shutil.which("pdftotext"):
        try:
            # -layout keeps columns, -nopgbrk avoids extra page breaks
            cmd = ["pdftotext", "-layout", "-nopgbrk"]
            if max_pages is not None:
                # pdftotext has -f firstpage -l lastpage
                cmd += ["-f", "1", "-l", str(max_pages)]
            cmd += [path, "-"]
            out = subprocess.run(cmd, capture_output=True, check=True, timeout=timeout)
            return out.stdout.decode("utf-8", errors="ignore")
        except Exception:
            pass

    # 2) PyPDF2 — pure Python fallback
    if "pypdf2" in engines:
        try:
            import PyPDF2
            text = []
            with open(path, "rb") as fh:
                r = PyPDF2.PdfReader(fh)
                n = len(r.pages)
                limit = min(max_pages, n) if max_pages else n
                for i in range(limit):
                    try:
                        pg = r.pages[i]
                        t = pg.extract_text() or ""
                        text.append(t)
                    except Exception:
                        continue
            t = "\n".join(text)
            if t.strip():
                return t
        except Exception:
            pass

    # 3) pdfminer.six — last resort; constrain pages, quiet logging
    if "pdfminer" in engines:
        try:
            from pdfminer.high_level import extract_text
            if max_pages:
                text = extract_text(path, page_numbers=set(range(max_pages))) or ""
            else:
                text = extract_text(path) or ""
            return text
        except Exception:
            # swallow weird font errors etc.
            return ""

    return ""

def find_files_with_all_words_single_line(root_dir, words_to_find,
                                          ignore_case=True, whole_word=False,
                                          include_ext={".txt", ".md", ".json", ".log", ".pdf"}):
    flags = re.I if ignore_case else 0
    pats = [
        (re.compile(r'\b' + re.escape(w) + r'\b', flags) if whole_word
         else re.compile(re.escape(w), flags))
        for w in words_to_find
    ]
    hits = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if include_ext and ext.lower() not in include_ext:
                continue
            file_path = os.path.join(dirpath, filename)

            try:

                if ext.lower() == ".pdf":
                    text = extract_text_from_pdf(file_path, timeout=args.pdf_timeout,
                                                 max_pages=args.pdf_pages, engine_order=engine_order)
                    if not text:
                        continue
                    # Some PDFs are one giant “line” — synthesize lines if needed
                    lines = text.splitlines()
                    if len(lines) <= 1:
                        # fall back to sentence-ish chunks
                        lines = re.split(r'(?<=[.!?])\s+', text)

                    for lineno, ln in enumerate(lines, 1):
                        if all(p.search(ln) for p in pats):
                            hits.append((file_path, lineno, ln.rstrip("\n")))
                            break

                else:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, ln in enumerate(f, 1):
                            if all(p.search(ln) for p in pats):
                                hits.append((file_path, lineno, ln.rstrip("\n")))
                                break
            except Exception as e:
                print(f"Error reading or processing file {file_path}: {e}")
                continue
    return hits

def find_files_with_all_words(root_dir, words_to_find, ignore_case=True,
                              same_line=False, whole_word=True,
                              include_ext={".txt", ".md", ".json", ".log"}):
    matched_files = []

    # pre-compile simple tests
    flags = re.I if ignore_case else 0
    pats = [ (re.compile(r'\b'+re.escape(w)+r'\b', flags) if whole_word
              else re.compile(re.escape(w), flags)) for w in words_to_find ]

    # keep your existing 'search_words' for the cross-line branch
    search_words = [w.lower() for w in words_to_find] if ignore_case else words_to_find

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)

            # --- NEW: skip binaries by extension (avoids PDFs, etc.) ---
            _, ext = os.path.splitext(filename)
            if include_ext and ext.lower() not in include_ext:
                continue

            try:
                if ext.lower() == ".pdf":
                    file_content = extract_text_from_pdf(file_path)
                    if not file_content:
                        continue
                else:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()

            except Exception as e:
                print(f"Error extracting text from pdf {file_path}: {e}")
                continue

            if not os.path.isfile(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    if same_line:
                        # NEW: any single line must contain ALL words (any order)
                        for ln in f:
                            if all(p.search(ln) for p in pats):
                                matched_files.append(file_path)
                                break
                        continue  # done with this file

                    # ORIGINAL: your cross-line logic — leave as-is
                    file_content = f.read()
                    if ignore_case:
                        file_content = file_content.lower()
                    normalized_content = ' '.join(file_content.split())
                    all_words_found = True
                    for word in search_words:
                        if word not in normalized_content:
                            all_words_found = False
                            break
                    if all_words_found:
                        matched_files.append(file_path)

            except Exception as e:
                print(f"Error reading or processing file {file_path}: {e}")
                continue

    return matched_files

if __name__ == "__main__":
    import argparse, os, re

    ap = argparse.ArgumentParser(description="Find files containing all words.")
    ap.add_argument("--root", required=True, help="Root directory to search")
    ap.add_argument("--words", nargs="+", required=True, help="Words to find (all required)")
    ap.add_argument("--case-sensitive", dest="ignore_case", action="store_false",
                    help="Make matching case-sensitive (default: case-insensitive)")
    ap.set_defaults(ignore_case=True)

    # substring toggle -> sets whole_word = False when used
    ap.add_argument("--substring", dest="whole_word", action="store_false",
                    help="Match substrings instead of whole words (so 'Comparing' matches 'compar')")
    ap.set_defaults(whole_word=True)

    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--same-line", action="store_true",
                      help="Require all words on the same line (any order)")
    mode.add_argument("--cross-line", action="store_true",
                      help="Allow words anywhere in the file (cross-line)")

    ap.add_argument("--ext", action="append",
                    help="File extensions to include (e.g., --ext .md --ext .json). Default: .txt,.md,.json,.log")
    ap.add_argument("--pdf", action="store_true",
                    help="Include PDFs in search.")
    ap.add_argument("--pdf-timeout", type=int, default=15,
                    help="Seconds to allow external extractor (pdftotext). Default: 15")
    ap.add_argument("--pdf-pages", type=int, default=None,
                    help="Max pages per PDF to scan (speeds up bad PDFs).")
    ap.add_argument("--pdf-engine-order", default="pdftotext,pypdf2,pdfminer",
                    help="Comma list of engines to try in order.")    

    args = ap.parse_args()

    include_ext = set(args.ext) if args.ext else {".txt", ".md", ".json", ".log"}
    if args.pdf:
        include_ext.add(".pdf")

    engine_order = tuple(s.strip().lower() for s in args.pdf_engine_order.split(","))

    if args.same_line:
        hits = find_files_with_all_words_single_line(
            args.root, args.words,
            ignore_case=args.ignore_case,
            whole_word=args.whole_word,
            include_ext=include_ext
        )
        if hits:
            for path, lineno, text in hits:
                print(f"{path}:{lineno}:{text}")
        else:
            print("No lines found containing all specified words.")

    else:  # --cross-line
        hits = find_files_with_all_words(
            args.root, args.words,
            ignore_case=args.ignore_case,
            same_line=False,               # your original behavior
            whole_word=args.whole_word,    # <- use the same attribute
            include_ext=include_ext
        )

    if hits:
        print("Files found containing all specified words:")
        for p in hits:
            print("-", p)
    else:
        print("No files found containing all specified words.")
