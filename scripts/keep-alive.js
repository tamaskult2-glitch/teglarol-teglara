// Ez a szkript SEMMILYEN saját üzleti logikát nem tartalmaz — szándékosan.
// Csak megnyitja a valódi, éles tippelo.html oldalt egy fejnélküli Chrome-ban,
// és hagyja pár másodpercig futni, hogy a benne lévő pollData() / ESPN auto-korrekció
// lefusson — pontosan úgy, mintha egy valódi felhasználó nyitotta volna meg.

const { chromium } = require('playwright');

const URL = process.env.TIPPELO_URL;
const FB_ADMIN_SECRET = process.env.FB_ADMIN_SECRET || '';

if (!URL) {
  console.error('❌ Hiányzik a TIPPELO_URL környezeti változó (repo Settings → Secrets and variables → Actions → Variables).');
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();

  if (FB_ADMIN_SECRET) {
    // Az admin secret-et a valódi appban is localStorage-ban tárolják
    // (Admin panel → Firebase admin secret kezelő). Ugyanígy állítjuk be itt is,
    // MIELŐTT az oldal JS-e lefutna — így a bot ugyanazokkal a jogosultságokkal
    // rendelkezik, mint az admin böngészője, tehát a results/scores/etScores
    // mezők írása sem fog admin-jog hiányában elakadni.
    await context.addInitScript((secret) => {
      window.localStorage.setItem('fb_admin_secret', secret);
    }, FB_ADMIN_SECRET);
  }

  const page = await context.newPage();
  page.on('console', (msg) => console.log('[oldal]', msg.text()));
  page.on('pageerror', (err) => console.log('[oldal hiba]', err.message));

  console.log('→ Megnyitás:', URL);
  // FONTOS: NEM 'networkidle' — a tippelo.html szándékosan állandó SSE (EventSource)
  // kapcsolatot tart nyitva az élő szinkronhoz, emiatt a hálózat sosem lenne "idle",
  // a networkidle várakozás garantáltan időtúllépésbe futna. Elég, ha az oldal
  // betöltődött és a JS elindult ('load') — a lenti waitForTimeout már úgyis
  // biztosítja, hogy a pollData()/ESPN-korrekció lefusson.
  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });

  // Hagyjuk futni annyi ideig, hogy a poll lefusson és az ESPN summary lekérdezések
  // (amik önmagukban is 1-2mp-et vehetnek igénybe meccsenként) befejeződjenek.
  await page.waitForTimeout(20000);

  console.log('✓ Kész, szinkron lefutott.');
  await browser.close();
})().catch((err) => {
  console.error('❌ Hiba futás közben:', err);
  process.exit(1);
});
