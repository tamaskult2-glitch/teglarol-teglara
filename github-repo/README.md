# 🧱 Tégláról-téglára mérő

Független TISZA ígéretkövető oldal — [teglarol-teglara.hu](https://teglarol-teglara.hu)

## Fájlok

| Fájl | Leírás |
|------|--------|
| `index.html` | Az élő oldal (automatikusan generált) |
| `index.template.html` | HTML sablon (`__DATA_PLACEHOLDER__` jelölővel) |
| `data.json` | Ígéretek adatbázisa (ezt szerkeszted kézzel is) |
| `scripts/update.py` | Claude API frissítő script |
| `sitemap.xml` | Google indexáláshoz |
| `robots.txt` | Google indexáláshoz |
| `manifest.json` | PWA beállítások |
| `sw.js` | Service Worker (offline működés) |

## Automatikus frissítés

Minden nap **reggel 9:00**-kor (magyar idő) a GitHub Actions:
1. Futtatja a `scripts/update.py` scriptet
2. Claude API megnézi a friss híreket
3. Frissíti a `data.json`-t és az `index.html`-t
4. Commitolja és pusholja a változásokat
5. Netlify automatikusan deployolja az újabb verziót

## Beállítás

### 1. GitHub Secret hozzáadása
GitHub repo → Settings → Secrets and variables → Actions → New secret:
- Név: `ANTHROPIC_API_KEY`
- Érték: az Anthropic API kulcsod

### 2. Netlify GitHub kapcsolat
Netlify → Site → Site configuration → Build & deploy → Link to Git provider → GitHub → válaszd ezt a repót

### 3. Kézi frissítés indítása
GitHub → Actions → "Napi automatikus frissítés" → Run workflow

## Kézi adatfrissítés

Ha valamit kézzel akarsz frissíteni, szerkeszd a `data.json` fájlt:
- `"Változás"`: `"ígéret"` / `"bejelentve"` / `"folyamatban"` / `"kész"` / `"teljesítve"`
- `"Frissítés"`: `"2026-04-21"` (mai dátum)

Commit után Netlify automatikusan deployol.

## Költségek

| Szolgáltatás | Díj |
|--------------|-----|
| GitHub | Ingyenes |
| Netlify hosting | Ingyenes |
| Claude API (napi 1 futás) | ~$0.10-0.30/nap (~3-9 USD/hó) |
| .hu domain | ~2500 Ft/év |
