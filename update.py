#!/usr/bin/env python3
"""
Tégláról-téglára automatikus frissítő
Naponta fut GitHub Actions-ből, Claude API-t hív, frissíti az adatokat.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic csomag hiányzik: pip install anthropic")
    sys.exit(1)

TODAY = date.today().isoformat()
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data.json"
TEMPLATE_FILE = ROOT / "index.template.html"
OUTPUT_FILE = ROOT / "index.html"

def load_data():
    if not DATA_FILE.exists():
        # Ha nincs data.json, kinyerjük az index.html-ből
        print("data.json nem található, kinyerés index.html-ből...")
        html_file = ROOT / "index.html"
        if html_file.exists():
            import re
            content = html_file.read_text(encoding="utf-8")
            match = re.search(r'excelData = (\[.*?\]);', content, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                save_data(data)
                print(f"✓ data.json létrehozva ({len(data)} ígéret)")
                return data
        raise FileNotFoundError(f"Nem található: {DATA_FILE}")
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_html(data):
    """Beilleszti az adatokat a template-be és létrehozza az index.html-t"""
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    data_js = json.dumps(data, ensure_ascii=False)
    html = template.replace("excelData = __DATA_PLACEHOLDER__;",
                            f"excelData = {data_js};")
    # Frissíti a dátumot a fejlécben
    html = re.sub(
        r'Updated: \d{4}\.\d{2}\.\d{2}',
        f'Updated: {TODAY.replace("-", ".")}',
        html
    )
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"✓ index.html létrehozva ({len(html):,} byte)")

def ask_claude(data):
    """Claude API frissítő — Haiku modellel, web search nélkül"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Max 15 legfontosabb ígéret
    pending = [d for d in data if d["Változás"] not in ("kész", "teljesítve")]
    priority_order = {"azonnali": 0, "rovid": 1, "hosszu": 2}
    pending.sort(key=lambda x: priority_order.get(x.get("Prioritás","hosszu"), 2))
    pending = pending[:15]

    items_short = [{"i": d["TiSZa ígéret"][:60], "s": d["Változás"], "k": d["Kategória"]} for d in pending]

    prompt = f"""Magyar politikai frissítő. Dátum: {TODAY}.

TISZA Párt ígéretek aktuális státusza (amit tudsz a képzési adataidból és általános tudásodból):
{json.dumps(items_short, ensure_ascii=False)}

Ha bármelyik ígéretnél BIZTOS hogy változás történt (bejelentve/teljesítve), jelezd.
Ha nem tudod biztosan, NE változtasd.

Válasz CSAK JSON tömb:
[{{"TiSZa ígéret": "...", "Változás": "bejelentve", "Volt előrelépést jelentő bejelentés?": "igen - rövid leírás"}}]
Ha nincs biztos változás: []"""

    import time
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            break
        except Exception as e:
            err = str(e).lower()
            if ('overloaded' in err or 'rate_limit' in err) and attempt < 2:
                wait = (attempt + 1) * 60
                print(f"API limit, várakozás {wait}s... ({attempt+1}/3)")
                time.sleep(wait)
            else:
                print(f"API hiba (nem kritikus): {e}")
                return []

    # Összegyűjti a text válaszokat
    full_text = ""
    for block in message.content:
        if block.type == "text":
            full_text += block.text

    print(f"Claude válasz ({len(full_text)} karakter)")

    # JSON kinyerése
    json_match = re.search(r'\[.*\]', full_text, re.DOTALL)
    if not json_match:
        print("Nem találtam JSON választ, nincs változás")
        return []

    try:
        updates = json.loads(json_match.group())
        print(f"✓ {len(updates)} frissítés érkezett")
        return updates
    except json.JSONDecodeError as e:
        print(f"JSON parse hiba: {e}")
        return []

def apply_updates(data, updates):
    """Alkalmazza a Claude által visszaadott frissítéseket"""
    if not updates:
        print("Nincs frissítés")
        return data, 0

    updated_count = 0
    for update in updates:
        igeret_name = update.get("TiSZa ígéret", "")
        for item in data:
            if item["TiSZa ígéret"] == igeret_name:
                changed = False
                for key, value in update.items():
                    if key != "TiSZa ígéret" and item.get(key) != value:
                        print(f"  [{igeret_name[:40]}] {key}: {item.get(key)} → {value}")
                        item[key] = value
                        changed = True
                if changed:
                    item["Frissítés"] = TODAY
                    updated_count += 1
                break

    print(f"✓ {updated_count} ígéret frissítve")
    return data, updated_count

def update_sitemap():
    """Frissíti a sitemap.xml dátumát"""
    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        content = sitemap.read_text()
        content = re.sub(r'<lastmod>.*?</lastmod>', f'<lastmod>{TODAY}</lastmod>', content)
        sitemap.write_text(content)
        print("✓ sitemap.xml frissítve")

def main():
    print(f"=== Tégláról-téglára frissítő | {TODAY} ===\n")

    # Adatok betöltése
    data = load_data()
    print(f"Betöltve: {len(data)} ígéret\n")

    # Claude API frissítés (csak ha van API key)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        updates = ask_claude(data)
        data, count = apply_updates(data, updates)
        if count > 0:
            save_data(data)
            print(f"\n✓ data.json mentve ({count} változás)")
        else:
            print("\nNincs változás a data.json-ban")
    else:
        print("ANTHROPIC_API_KEY nincs beállítva, kihagyva")

    # HTML újragenerálás (mindig)
    build_html(data)
    update_sitemap()

    print(f"\n=== Kész ===")

if __name__ == "__main__":
    main()
