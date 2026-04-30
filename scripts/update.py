#!/usr/bin/env python3
"""Tégláról-téglára frissítő – optimalizált, alacsony API költség"""
import os, re, json
from datetime import date
from pathlib import Path
import anthropic

TODAY = date.today().isoformat()
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data.json"
TEMPLATE_FILE = ROOT / "index.template.html"
OUTPUT_FILE = ROOT / "index.html"


def load_data():
    if not DATA_FILE.exists():
        html_file = ROOT / "index.html"
        if html_file.exists():
            content = html_file.read_text(encoding="utf-8")
            match = re.search(r'excelData = (\[.*?\]);', content, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                save_data(data)
                return data
        raise FileNotFoundError(f"Nem található: {DATA_FILE}")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_html(data):
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    data_js = json.dumps(data, ensure_ascii=False)
    html = template.replace("excelData = __DATA_PLACEHOLDER__;", f"excelData = {data_js};")
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"index.html: {len(html):,} byte, datum: {TODAY}")


def ask_claude(data):
    """Optimalizalt API hivas: max 5 igeret, ultra-rovid prompt"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    pending = [d for d in data
               if d["Változás"] not in ("kész", "teljesítve")
               and d.get("Prioritás") == "azonnali"]
    pending = pending[:5]

    if not pending:
        print("Nincs azonnali frissitendo igeret.")
        return []

    items = "\n".join([f"{i+1}. {d['TiSZa ígéret'][:50]} [{d['Változás']}]"
                       for i, d in enumerate(pending)])

    prompt = f"""Datum: {TODAY}. TISZA Part igeretek:
{items}

Ha BIZTOS statuszvaltozas van, valaszolj: [{{"n":1,"s":"bejelentve"}}]
Ha nincs valtozas: []
Csak JSON, semmi mas!"""

    print(f"Prompt: {len(prompt)} kar, {len(pending)} igeret")

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
    except Exception as e:
        print(f"API hiba: {e}")
        return []

    u = msg.usage
    cost = (u.input_tokens / 1_000_000 * 0.80) + (u.output_tokens / 1_000_000 * 4.00)
    print(f"Tokens: in={u.input_tokens}, out={u.output_tokens}, ~${cost:.4f}")

    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)

    try:
        updates = json.loads(text)
    except Exception:
        print(f"Nem JSON valasz: {text[:200]}")
        return []

    result = []
    for u in updates:
        if 'n' in u and 's' in u:
            idx = u['n'] - 1
            if 0 <= idx < len(pending):
                result.append({"TiSZa ígéret": pending[idx]['TiSZa ígéret'], "Változás": u['s']})
    return result


def apply_updates(data, updates):
    if not updates:
        return 0
    count = 0
    for upd in updates:
        for d in data:
            if d['TiSZa ígéret'] == upd['TiSZa ígéret']:
                if d.get('Változás') != upd.get('Változás'):
                    d['Változás'] = upd['Változás']
                    d['Frissítés'] = TODAY
                    count += 1
                    print(f"  Valtozas: {d['TiSZa ígéret'][:50]}")
                break
    return count


def main():
    print(f"=== Teglarol-teglara | {TODAY} ===")
    data = load_data()
    print(f"Adat: {len(data)} igeret")

    updates = ask_claude(data)
    changed = apply_updates(data, updates)

    if changed > 0:
        save_data(data)
        print(f"{changed} valtozas mentve")
    else:
        print("Nincs uj valtozas")

    build_html(data)
    print("=== Kesz ===")


if __name__ == "__main__":
    main()
