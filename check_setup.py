"""Step 2 smoke test: confirms the LLM and every tool work before we build agents.

Run:  python check_setup.py
"""
from launchscout.config import MODEL, OUTPUT_DIR, check_env, get_llm
from launchscout.tools import file_writer_tool, scrape_tool, search_tool


def main() -> None:
    print(f"Model: {MODEL}\n")
    for p in check_env():
        print(f"[!] {p}")

    # 1. LLM
    try:
        reply = get_llm().call("Reply with exactly: LLM OK")
        print(f"[ok] LLM replied: {reply.strip()[:60]}")
    except Exception as e:
        print(f"[x] LLM failed: {e}")

    # 2. Web search
    try:
        result = search_tool().run(search_query="healthy meal box Coimbatore")
        print(f"[ok] Serper search returned {len(str(result))} chars")
    except Exception as e:
        print(f"[x] Serper search failed: {e}")

    # 3. Scraper
    try:
        text = scrape_tool().run(website_url="https://example.com")
        print(f"[ok] Scraper read {len(str(text))} chars from example.com")
    except Exception as e:
        print(f"[x] Scraper failed: {e}")

    # 4. File writer
    try:
        file_writer_tool().run(filename="_check.md", content="ok", overwrite=True)
        f = OUTPUT_DIR / "_check.md"
        print(f"[ok] File writer saved {f}" if f.exists() else "[x] File writer: file not found")
        f.unlink(missing_ok=True)
    except Exception as e:
        print(f"[x] File writer failed: {e}")


if __name__ == "__main__":
    main()
