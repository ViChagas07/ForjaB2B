async (page) => {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.goto("https://forja-b2b.vercel.app/pt-BR/catalog", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.locator("article img").first().waitFor({ timeout: 40000 });
  await page.waitForTimeout(3500);
  const imgs = await page.evaluate(() => {
    const list = [...document.querySelectorAll("article img")];
    return { cards: document.querySelectorAll("article").length, ok: list.filter(i => i.complete && i.naturalWidth > 0).length, fotos: list.filter(i => (i.getAttribute("src") || "").includes("/catalog/photos/")).length, ilustracoes: list.filter(i => (i.getAttribute("src") || "").includes("/catalog/illustrations/")).length };
  });
  await page.screenshot({ path: "D:\\ForjaB2B\\.playwright-mcp\\prompt10-lote2-deployado.png" });
  return imgs;
}
