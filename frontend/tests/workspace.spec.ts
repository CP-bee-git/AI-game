import { expect, test } from "@playwright/test";

const configuration = { backend: "dify", model: "DeepSeek 评分 / 千问报告", provider: "Dify", image_ocr: "千问视觉", matching: "DeepSeek", chat_configured: true, vision_configured: true };
const orchestration = { backend: "dify", workflows: { profile: true, analysis: true, chat: true }, agents: { scoring: "DeepSeek", report: "千问", media: "豆包" }, media_enabled: false, media_capabilities: { image: false, video: false } };

test("managed workspace hides keys, collapses records and respects disabled media and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  await page.route("**/api/v1/orchestration", (route) => route.fulfill({ json: orchestration }));
  let mediaCalls = 0;
  page.on("request", (request) => { if (request.method() === "POST" && request.url().endsWith("/api/v1/media")) mediaCalls++; });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "评分与写作，各有分工" })).toBeVisible();
  await expect(page.getByLabel("千问 / 阿里云 API Key")).toHaveCount(0);
  const collapse = page.getByRole("button", { name: "收起工作记录" });
  await collapse.click();
  await expect(page.locator("#context-content")).toBeHidden();
  await expect(page.getByRole("button", { name: "展开工作记录" })).toBeFocused();
  await page.getByRole("button", { name: "展开工作记录" }).press("Enter");
  await expect(page.getByRole("button", { name: "载入示例" })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成内容" })).toBeDisabled();
  expect(mediaCalls).toBe(0);
  await expect(page.getByText("服务连接", { exact: true })).toBeVisible();
  await expect(page.locator(".upload-section")).toHaveCSS("animation-name", "none");
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("enabled video creation requires consent, queries status and renders a playable result", async ({ page }) => {
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  await page.route("**/api/v1/orchestration", (route) => route.fulfill({ json: { ...orchestration, media_enabled: true, media_capabilities: { image: true, video: true } } }));
  const task = { task_id: "video-test", request_id: "", kind: "video", status: "queued", urls: [] as string[] };
  let submitted: Record<string, unknown> = {};
  await page.route("**/api/v1/media", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { ...task, request_id: submitted.request_id } });
  });
  await page.route("**/api/v1/media/video-test", (route) => route.fulfill({ json: { ...task, status: "succeeded", urls: ["https://example.com/generated.mp4"] } }));
  await page.goto("/");
  await page.getByRole("button", { name: "职业短片", exact: true }).click();
  await page.getByLabel("描述你想呈现的场景").fill("数据分析师在办公室检查报表，不出现身份信息。");
  await expect(page.getByRole("button", { name: "生成内容" })).toBeDisabled();
  await page.locator("#media").getByRole("checkbox").check();
  await page.getByRole("button", { name: "生成内容" }).click();
  await expect(page.locator(".media-result")).toContainText("排队中");
  expect(submitted.consent).toBe(true);
  expect(submitted.request_id).toMatch(/^[a-zA-Z0-9_-]{16,64}$/);
  await page.getByRole("button", { name: "查询任务状态" }).click();
  await expect(page.getByLabel("生成的职业短片")).toHaveAttribute("controls", "");
});

test("completed interview can retry only its pending summary", async ({ page }) => {
  await page.route("**/api/v1/model-config", (route) => route.fulfill({ json: configuration }));
  await page.route("**/api/v1/orchestration", (route) => route.fulfill({ json: orchestration }));
  const interview = { session_id: "interview-test", job_title: "数据分析练习", status: "completed", turns: [{ question: "如何核对数据？", answer: "检查原始记录。", score: 3, feedback: "补充检查过程" }], summary: ["回答已保存，复盘待生成"], summary_pending: true, overall_score: 3 };
  await page.route("**/api/v1/interviews", (route) => route.fulfill({ status: 201, json: interview }));
  let retries = 0;
  await page.route("**/api/v1/interviews/interview-test/summary", async (route) => {
    retries++;
    await route.fulfill({ json: { ...interview, summary_pending: false, summary: ["下次说明数据核对的方法。"] } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "载入示例" }).click();
  await page.getByRole("button", { name: "确认信息，查看匹配" }).click();
  await page.getByRole("button", { name: "开始匹配" }).click();
  await page.locator(".match-row").first().getByRole("button", { name: "面试", exact: true }).click();
  await page.getByRole("button", { name: "重新生成复盘" }).click();
  await expect(page.locator(".interview-summary")).toContainText("数据核对的方法");
  await expect(page.getByRole("button", { name: "重新生成复盘" })).toHaveCount(0);
  expect(retries).toBe(1);
});

test("profile review exposes extracted fields and sends user corrections when confirmed", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "载入示例" }).click();
  await page.locator(".profile-review > summary").click();
  await page.getByLabel("学校", { exact: true }).first().fill("核对后的合成大学");
  await page.getByLabel("意向城市").fill("上海、杭州");
  const confirmation = page.waitForRequest((request) => request.url().endsWith("/profile/confirm"));
  await page.getByRole("button", { name: "确认信息，查看匹配" }).click();
  const payload = (await confirmation).postDataJSON();
  expect(payload.education[0].school).toBe("核对后的合成大学");
  expect(payload.preferences.cities).toEqual(["上海", "杭州"]);
  await expect(page.getByLabel("意向城市")).toBeDisabled();
  await page.getByRole("button", { name: "修改已确认信息" }).click();
  await expect(page.getByLabel("意向城市")).toBeEnabled();
  await expect(page.locator("#analysis")).toHaveCount(0);
});
