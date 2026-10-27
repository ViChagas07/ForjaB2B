async (page) => {
  const events = [];
  page.on("requestfailed", (req) => events.push({ tipo: "FALHA", url: req.url().slice(0, 90), erro: req.failure() && req.failure().errorText, ms: Date.now() - t0 }));
  page.on("requestfinished", (req) => { if (req.url().includes("/api/") || (req.resourceType() === "image")) events.push({ tipo: "OK", url: req.url().slice(0, 90), ms: Date.now() - t0 }); });
  var t0 = Date.now();
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.goto("https://forja-b2b.vercel.app/pt-BR", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(30000);
  const state = await page.evaluate(() => ({
    cards: document.querySelectorAll("article").length,
    vazio: document.body.innerText.includes("Nenhum destaque"),
    imgsOk: [...document.querySelectorAll("article img")].filter(i => i.complete && i.naturalWidth > 0).length,
    imgsTotal: document.querySelectorAll("article img").length
  }));
  return { state, eventos: events.slice(0, 30) };
}
