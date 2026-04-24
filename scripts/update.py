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
    """Claude API-t kér meg a frissítésre"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Csak azokat küldjük, ahol a Változás nem "kész"/"teljesítve"
    pending = [d for d in data if d["Változás"] not in ("kész", "teljesítve")]

    prompt = f"""Te egy magyar politikai adatelemző vagy. A mai dátum: {TODAY}.

Az alábbi lista a TISZA Párt (Magyar Péter) ígéreteit tartalmazza, amelyek még nem teljesültek.
Keresd meg az interneten (web search eszközzel) a mai friss híreket, és frissítsd az adatokat.

FONTOS SZABÁLYOK:
1. Csak akkor változtasd meg a "Változás" mezőt, ha BIZTOS forrásod van rá
2. "Változás" lehetséges értékei: "ígéret", "bejelentve", "folyamatban", "kész", "teljesítve"
3. Ha frissítettél valamit, add meg a "Forrás link"-et
4. A "Frissítés" mezőt állítsd "{TODAY}"-re ha változtattal
5. Ha nincs új információ egy tételnél, NE változtasd meg
6. Válaszolj CSAK valid JSON tömbként, semmi más szöveg

Az ígéretek listája (JSON):
{json.dumps(pending, ensure_ascii=False, indent=1)}

Válaszolj egy JSON tömbként, ahol csak a MEGVÁLTOZOTT tételeket szerepelted.
Minden megváltozott tételnél add meg a "TiSZa ígéret" mezőt azonosításhoz.
Ha semmi nem változott, válaszolj üres tömbbel: []"""

    print("Claude API hívás...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

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
