import { getStore } from "@netlify/blobs";

export default async (req, context) => {
  // CORS headers
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Content-Type": "application/json",
  };

  // OPTIONS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers });
  }

  try {
    const store = getStore("visitors");
    const today = new Date().toISOString().slice(0, 10);      // "2026-04-21"
    const month = today.slice(0, 7);                           // "2026-04"

    // Beolvasás
    const [totalRaw, todayRaw, monthRaw] = await Promise.all([
      store.get("total"),
      store.get("day_" + today),
      store.get("month_" + month),
    ]);

    const BASE = 320; // induló alap
    let total = Math.max(parseInt(totalRaw || "0") || 0, BASE);
    let dayCount = parseInt(todayRaw || "0") || 0;
    let monthCount = parseInt(monthRaw || "0") || 0;

    if (req.method === "POST") {
      // Növelés
      total += 1;
      dayCount += 1;
      monthCount += 1;

      await Promise.all([
        store.set("total", String(total)),
        store.set("day_" + today, String(dayCount)),
        store.set("month_" + month, String(monthCount)),
      ]);
    }

    return new Response(
      JSON.stringify({ total, today: dayCount, month: monthCount }),
      { headers }
    );

  } catch (err) {
    // Fallback ha a Blobs nem elérhető
    return new Response(
      JSON.stringify({ total: 320, today: 1, month: 1, error: err.message }),
      { status: 200, headers }
    );
  }
};

export const config = {
  path: "/api/counter",
};
