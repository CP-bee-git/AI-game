// 截图验收脚本（可重复运行）
import { test } from "@playwright/test";

const viewports = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "phone-390", width: 390, height: 844 },
  { name: "phone-360", width: 360, height: 800 },
];

for (const viewport of viewports) {
  test(`screenshots ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/developer");
    await page.waitForTimeout(600);
    await page.screenshot({ path: `/tmp/shots/developer-${viewport.name}.png`, fullPage: true });
    await page.goto("/");
    await page.waitForTimeout(800);
    await page.screenshot({ path: `/tmp/shots/home-${viewport.name}.png`, fullPage: true });
    // check horizontal overflow
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (overflow) throw new Error(`horizontal overflow on ${viewport.name}`);
  });
}
