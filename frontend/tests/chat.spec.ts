import { expect, test } from "@playwright/test";

const configuration = {
  model: "qwen-plus", provider: "阿里云百炼 · 千问", image_ocr: "千问视觉模型",
  matching: "规则匹配", chat_configured: true, vision_configured: true, region: "china",
};
type Payload = { messages: Array<{ role: string; content: string }> };

test("chat works without a resume, consent checkbox or demo metadata and keeps conversational context", async ({ page }) => {
  let releaseMetadata!: () => void;
  const gate = new Promise<void>((resolve) => { releaseMetadata = resolve; });
  const payloads: Payload[] = [];
  let uploads = 0;
  page.on("request", (request) => { if (request.url().includes("/resumes/") && request.method() === "POST") uploads++; });
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  await page.route("**/api/v1/demo/china", async (route) => { await gate; await route.fulfill({ json: { notice: "测试用示例说明", sources: [] } }); });
  await page.route("**/api/v1/chat", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({ json: { reply: payloads.length === 2 ? "<img src=x onerror=alert(1)> 这是文本。" : "可以先说说你感兴趣的岗位。" } });
  });
  try {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "直接聊天" })).toBeVisible();
    await expect(page.getByText("连接已验证", { exact: true })).toBeVisible();
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await page.getByLabel("想聊什么").fill("我还没有简历，能聊聊职业方向吗？");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect(page.locator(".chat-message.assistant")).toContainText("感兴趣的岗位");
    const metadataFinished = page.waitForResponse((response) => response.url().endsWith("/api/v1/demo/china"), { timeout: 10000 });
    releaseMetadata();
    await metadataFinished;
    await page.getByLabel("想聊什么").fill("我对数据分析感兴趣。");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect(page.locator(".chat-message.assistant").last()).toContainText("<img src=x onerror=alert(1)>");
    await expect(page.locator(".chat-messages img")).toHaveCount(0);
    expect(payloads[1]).toEqual({ messages: [
      { role: "user", content: "我还没有简历，能聊聊职业方向吗？" },
      { role: "assistant", content: "可以先说说你感兴趣的岗位。" },
      { role: "user", content: "我对数据分析感兴趣。" },
    ] });
    expect(uploads).toBe(0);
    await expect(page.locator("#analysis")).toHaveCount(0);
    await page.getByRole("button", { name: "清空对话" }).click();
    await expect(page.getByRole("log", { name: "聊天记录" })).toHaveCount(0);
    await page.getByLabel("想聊什么").fill("换个话题，想练习自我介绍。");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(1);
    expect(payloads[2].messages).toHaveLength(1);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByRole("log", { name: "聊天记录" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "载入示例" })).toBeEnabled();
  } finally {
    releaseMetadata();
  }
});

test("chat on a narrow phone preserves the question after a cloud failure and can retry", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  let calls = 0;
  await page.route("**/api/v1/chat", async (route) => {
    calls++;
    await route.fulfill(calls === 1
      ? { status: 402, json: { detail: "阿里云账户计费状态异常，请处理后重试。", error_code: "cloud_billing" } }
      : { json: { reply: "我们可以从你的学习经历开始。" } });
  });
  await page.goto("/");
  await page.getByLabel("想聊什么").fill("没有实习经历，怎么介绍自己？");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(page.locator("#chat").getByRole("alert")).toContainText("计费状态异常");
  await expect(page.getByLabel("想聊什么")).toHaveValue("没有实习经历，怎么介绍自己？");
  await expect(page.locator(".chat-message")).toHaveCount(0);
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(page.locator(".chat-message.assistant")).toContainText("学习经历");
  await expect(page.locator("#chat").getByRole("alert")).toHaveCount(0);
  await expect(page.locator(".chat-privacy")).toHaveCSS("color", "rgb(0, 0, 0)");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("chat only requires the cloud connection and provides a direct configuration button", async ({ page }) => {
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: { ...configuration, chat_configured: false } }));
  await page.goto("/");
  await page.getByLabel("想聊什么").fill("想聊聊岗位选择。");
  await expect(page.getByRole("button", { name: "发送", exact: true })).toBeDisabled();
  await page.locator("#chat").getByRole("button", { name: "连接千问", exact: true }).click();
  await expect(page.locator("#cloud-config")).toHaveAttribute("open", "");
  await expect(page.getByLabel("千问 / 阿里云 API Key")).toBeFocused();
});

test("chat trims old complete turns when conversation reaches the context budget", async ({ page }) => {
  const payloads: Payload[] = [];
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  await page.route("**/api/v1/chat", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({ json: { reply: "答".repeat(4000) } });
  });
  await page.goto("/");
  for (let index = 0; index < 4; index++) {
    await page.getByLabel("想聊什么").fill("问".repeat(3999) + index);
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(index + 1);
  }
  expect(payloads[3].messages).toHaveLength(5);
  expect(payloads[3].messages.reduce((length, message) => length + message.content.length, 0)).toBe(20000);
  expect(payloads[3].messages[0].content).toBe("问".repeat(3999) + 1);
  expect(payloads[3].messages.at(-1)?.role).toBe("user");
});
