import { expect, test } from "@playwright/test";

const disconnected = {
  model: "qwen-plus",
  provider: "阿里云百炼 · 千问",
  image_ocr: "千问视觉模型",
  matching: "规则匹配",
  chat_configured: false,
  vision_configured: false,
  region: "china",
};

test("cloud connection verifies, clears the password field, survives refresh and can be removed", async ({ page }) => {
  let config = { ...disconnected };
  let posted: Record<string, unknown> | null = null;
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: config }));
  await page.route("**/api/v1/model/configure", async (route) => {
    if (route.request().method() === "DELETE") {
      config = { ...disconnected };
    } else {
      posted = route.request().postDataJSON();
      config = { ...disconnected, chat_configured: true, vision_configured: true, model: "qwen-turbo", region: "singapore" };
    }
    await route.fulfill({ json: config });
  });
  await page.goto("/");
  await expect(page.getByLabel("千问 / 阿里云 API Key")).toHaveAttribute("type", "password");
  await expect(page.getByRole("button", { name: "验证并连接" })).toBeDisabled();
  await page.getByLabel("千问 / 阿里云 API Key").fill("test-api-key-not-a-real-credential");
  await page.getByLabel("服务区域").selectOption("singapore");
  await page.getByLabel("聊天模型").fill("qwen-turbo");
  await page.getByRole("button", { name: "验证并连接" }).click();
  await expect(page.getByRole("status")).toContainText("连接验证成功");
  expect(posted).toEqual({ api_key: "test-api-key-not-a-real-credential", region: "singapore", model: "qwen-turbo" });
  await expect(page.getByLabel("千问 / 阿里云 API Key")).toHaveValue("");
  await expect(page.getByText("连接已验证", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Object.values(localStorage))).not.toContain("test-api-key-not-a-real-credential");
  await page.reload();
  await expect(page.getByText("连接已验证", { exact: true })).toBeVisible();
  await expect(page.getByLabel("服务区域")).toHaveValue("singapore");
  await expect(page.getByLabel("聊天模型")).toHaveValue("qwen-turbo");
  await page.getByRole("button", { name: "清除临时密钥" }).click();
  await expect(page.getByRole("status")).toContainText("临时密钥已清除");
  await expect(page.getByText("等待连接", { exact: true })).toBeVisible();
});

test("rejected cloud keys show a useful error without exposing the key", async ({ page }) => {
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: disconnected }));
  await page.route("**/api/v1/model/configure", (route) => route.fulfill({
    status: 401,
    json: { detail: "API Key 无效：test-invalid-key，请检查服务区域。" },
  }));
  await page.goto("/");
  await page.getByLabel("千问 / 阿里云 API Key").fill("test-invalid-key");
  await page.getByRole("button", { name: "验证并连接" }).click();
  await expect(page.locator("#cloud-config").getByRole("alert")).toContainText("API Key 无效");
  await expect(page.locator("#cloud-config").getByRole("alert")).not.toContainText("test-invalid-key");
  await expect(page.getByText("等待连接", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "验证并连接" })).toBeEnabled();
});

test("cloud settings remain usable on a narrow phone", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: disconnected }));
  await page.goto("/#cloud-config");
  await expect(page.getByRole("heading", { name: /一枚密钥，.*开启千问的能力/  })).toBeVisible();
  await page.getByLabel("千问 / 阿里云 API Key").fill("test-phone-key");
  await page.getByLabel("服务区域").selectOption("china");
  await expect(page.getByRole("button", { name: "验证并连接" })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("delayed initial settings preserve the region and model the user already edited", async ({ page }) => {
  let releaseInitialConfig!: () => void;
  const initialConfigGate = new Promise<void>((resolve) => { releaseInitialConfig = resolve; });
  let configured = false;
  let posted: Record<string, unknown> | null = null;
  const saved = { ...disconnected, chat_configured: true, vision_configured: true };
  const updated = { ...saved, region: "singapore", model: "qwen-turbo" };
  await page.route("**/api/v1/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v1/model-config", async (route) => {
    // Strict Mode may start initialization twice; hold both initial reads.
    if (!configured) await initialConfigGate;
    await route.fulfill({ json: configured ? updated : saved });
  });
  await page.route("**/api/v1/model/configure", async (route) => {
    posted = route.request().postDataJSON();
    configured = true;
    await route.fulfill({ json: updated });
  });
  const initialRequest = page.waitForRequest("**/api/v1/model-config");
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await initialRequest;
  await page.getByLabel("千问 / 阿里云 API Key").fill("test-delayed-key-not-a-real-credential");
  await page.getByLabel("服务区域").selectOption("singapore");
  await page.getByLabel("聊天模型").fill("qwen-turbo");
  releaseInitialConfig();
  await expect(page.getByText("连接已验证", { exact: true })).toBeVisible();
  await expect(page.getByLabel("服务区域")).toHaveValue("singapore");
  await expect(page.getByLabel("聊天模型")).toHaveValue("qwen-turbo");
  await page.getByRole("button", { name: "验证并更新连接" }).click();
  await expect(page.getByRole("status")).toContainText("连接验证成功");
  expect(posted).toEqual({ api_key: "test-delayed-key-not-a-real-credential", region: "singapore", model: "qwen-turbo" });
});
