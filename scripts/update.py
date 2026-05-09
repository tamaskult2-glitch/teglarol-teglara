#!/usr/bin/env python3
"""Tégláról-téglára frissítő – web search + előrelépés frissítés"""
import os, re, json
from datetime import date
from pathlib import Path
import anthropic

TODAY = date.today().isoformat()
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data.json"
TEMPLATE_FILE = ROOT / "index.template.html"
OUTPUT_FILE = ROOT / "index.html"

# Hány téglát vizsgáljon meg egyszerre
BATCH_SIZE = 5


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    # Fallback: kinyerjük az index.html-ből
    html_file = ROOT / "index.html"
    if html_file.exists():
        content = html_file.read_text(encoding="utf-8")
        start = content.find("const excelData = [") + len("const excelData = ")
        end = content.find("\n];", start) + 2
        raw = re.sub(r",\s*\]$", "\n]", content[start:end].strip())
        data = json.loads(raw)
        save_data(data)
        return data
    raise FileNotFoundError(f"Nem található: {DATA_FILE}")


def save_data(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_html(data):
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    data_js = json.dumps(data, ensure_ascii=False)
    html = template.replace(
        "excelData = __DATA_PLACEHOLDER__;", f"excelData = {data_js};"
    )
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"index.html: {len(html):,} byte, datum: {TODAY}")


def ask_claude_batch(client, batch):
    """Egy batch téglára kér frissítést – web search csak ha régi adat"""
    from datetime import datetime, timedelta

    # Web search csak ha van 7 napnál régebben frissített tégla a batch-ben
    stale = [d for d in batch
             if d.get("Frissítés", "2000-01-01") < (date.today() - timedelta(days=7)).isoformat()]
    use_web = len(stale) > 0

    items_text = "\n".join(
        f"{i+1}. [{d['Változás']}] {d['TiSZa ígéret'][:60]}"
        f" | Utolsó: {d.get('Frissítés','?')}"
        for i, d in enumerate(batch)
    )

    prompt = f"""Mai dátum: {TODAY}. Tisza Párt kormány ígéretek Magyarország.
{"Keresd meg a legfrissebb híreket az alábbi ígéretekhez:" if use_web else "Tudásod alapján van-e friss fejlemény ("+TODAY+") az alábbi ígéreteknél?"}

{items_text}

Válaszolj CSAK JSON-ban:
[{{"n":1,"elore":"új előrelépés max 120 kar","datum":"{TODAY}","forras":"url","valtozas":"bejelentve|kész|igéret"}}]
Ha nincs változás: []"""

    tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web else []

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            tools=tools if tools else anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  API hiba: {e}")
        return []

    u = msg.usage
    cost = (u.input_tokens / 1_000_000 * 0.80) + (u.output_tokens / 1_000_000 * 4.00)
    print(f"  Tokens: in={u.input_tokens}, out={u.output_tokens}, ~${cost:.4f}")

    # Összegyűjtjük a text blokkokat
    text = "".join(
        b.text for b in msg.content if hasattr(b, "text") and b.type == "text"
    ).strip()

    if not text:
        return []

    # JSON kinyerés
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    # Ha csak [] akkor üres
    text = text.strip()
    if text == "[]":
        return []

    try:
        updates = json.loads(text)
        return updates if isinstance(updates, list) else []
    except Exception:
        # Próbáljuk kinyerni a JSON tömböt
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        print(f"  Nem JSON: {text[:150]}")
        return []


def apply_updates(data, batch, updates):
    """Updates alkalmazása a batch-re"""
    count = 0
    for upd in updates:
        n = upd.get("n")
        if not n or not isinstance(n, int):
            continue
        idx = n - 1
        if idx < 0 or idx >= len(batch):
            continue

        igeret_nev = batch[idx]["TiSZa ígéret"]
        for d in data:
            if d["TiSZa ígéret"] == igeret_nev:
                changed = False

                if upd.get("elore") and upd["elore"] != d.get("Volt előrelépést jelentő bejelentés?"):
                    d["Volt előrelépést jelentő bejelentés?"] = upd["elore"]
                    changed = True

                if upd.get("forras"):
                    url = upd["forras"].strip()
                    # Ha nincs protokoll, egészítsük ki
                    if not url.startswith("http://") and not url.startswith("https://"):
                        url = "https://" + url
                    if url != d.get("Forrás link"):
                        d.["Forrás link"] = url
                        changed = True



                if upd.get("valtozas") and upd["valtozas"] != d.get("Változás"):
                    d["Változás"] = upd["valtozas"]
                    changed = True

                if changed:
                    d["Frissítés"] = TODAY
                    count += 1
                    print(f"  ✓ {igeret_nev[:55]}")
                break
    return count


def get_subscribers():
    """Feliratkozók beolvasása subscribers.json-ból"""
    subs_file = ROOT / "subscribers.json"
    if not subs_file.exists():
        print("  subscribers.json nem található")
        return []
    try:
        data = json.loads(subs_file.read_text(encoding="utf-8"))
        emails = data.get("emails", [])
        print(f"  Feliratkozók: {len(emails)} db")
        return emails
    except Exception as e:
        print(f"  subscribers.json hiba: {e}")
        return []


def send_notifications(changed_count):
    """EmailJS REST API-n keresztül értesíti a feliratkozókat"""
    import urllib.request
    emails = get_subscribers()
    if not emails:
        return

    service_id = "service_x5huqxn"
    template_id = "template_pfrf10g"
    public_key  = "0k7yH8d4u-BjgACd1"

    sent = 0
    for email in emails:
        payload = json.dumps({
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,
            "template_params": {
                "email": email,
                "name": "Feliratkozó",
                "db": str(changed_count)
            }
        }).encode()
        try:
            req = urllib.request.Request(
                "https://api.emailjs.com/api/v1.0/email/send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req) as r:
                if r.status == 200:
                    sent += 1
        except Exception as e:
            print(f"  EmailJS hiba ({email[:20]}): {e}")

    print(f"  Értesítő elküldve: {sent}/{len(emails)} feliratkozónak")


def main():
    print(f"=== Teglarol-teglara | {TODAY} ===")
    data = load_data()
    print(f"Adat: {len(data)} igeret")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Prioritás szerint sorba rendezés: azonnali > rovid > hosszu
    # + régebben frissítettek előre
    priority_order = {"Azonnali": 0, "azonnali": 0, "rovid": 1, "hosszu": 2}
    candidates = sorted(
        [d for d in data if d.get("Változás") not in ("kész", "teljesítve")],
        key=lambda d: (
            priority_order.get(d.get("Prioritás", "rovid"), 1),
            d.get("Frissítés", "2000-01-01"),
        ),
    )

    total_changed = 0
    batches = [candidates[i:i+BATCH_SIZE] for i in range(0, min(len(candidates), BATCH_SIZE * 2), BATCH_SIZE)]
    for bi, batch in enumerate(batches):
        if bi > 0:
            print("  Varakozas 70mp (rate limit)...")
            import time; time.sleep(70)
        print(f"\nBatch {bi+1}: {len(batch)} igeret ({batch[0]['TiSZa ígéret'][:30]}...)")
        updates = ask_claude_batch(client, batch)
        if updates:
            changed = apply_updates(data, batch, updates)
            total_changed += changed
        else:
            print("  Nincs frissités")

    if total_changed > 0:
        save_data(data)
        print(f"\n{total_changed} valtozas mentve → data.json")
        send_notifications(total_changed)
    else:
        print("\nNincs uj valtozas")

    build_html(data)
    print("=== Kesz ===")


if __name__ == "__main__":
    main()
