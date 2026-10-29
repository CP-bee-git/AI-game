import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("Chinese synthetic demo completes profile stars, ten real careers, matching, diagnosis, interview and downloads", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "加载中国样例 · 合成简历" }).click();
  await expect(page.getByLabel("技能（可修改，逗号分隔）")).toHaveValue(/Python/);
  await expect(page.locator("#analysis")).toHaveCount(0);
  await page.getByRole("button", { name: "确认画像并进入岗位匹配" }).click();
  await expect(page.locator(".career-row")).toHaveCount(10);
  await expect(page.locator(".dimension").first()).toBeVisible();
  await expect(page.locator(".dimension").first().getByRole("img")).toHaveAttribute("aria-label", /5 星/);
  await expect(page.locator(".catalog-note")).toContainText("O*NET");
  await expect(page.locator(".career-row").first()).not.toContainText("（演示）");
  await page.locator(".career-source").first().locator("summary").click();
  await expect(page.locator(".career-source").first().getByRole("link")).toHaveAttribute("href", /https:\/\/www\.onetonline\.org\/link\/summary\//);
  const profileDownloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载完整画像报告 HTML" }).click();
  const profileDownload = await profileDownloadEvent;
  expect(profileDownload.suggestedFilename()).toBe("careerpilot-profile.html");
  const profilePath = await profileDownload.path();
  expect(profilePath).not.toBeNull();
  const profileHtml = await readFile(profilePath!, "utf8");
  expect(profileHtml).toContain("onetonline.org");
  await page.getByRole("button", { name: "开始匹配" }).click();
  await expect(page.locator(".match-row")).toHaveCount(10);
  await expect(page.locator(".match-row").first()).toContainText("数据分析助理");
  const biRow = page.locator(".match-row").filter({ hasText: "BI报表助理（演示）" });
  await biRow.getByRole("button", { name: "诊断", exact: true }).click();
  await expect(page.locator(".report-panel")).toContainText("powerbi");
  const reportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载诊断报告 HTML" }).click();
  expect((await reportDownload).suggestedFilename()).toBe("careerpilot-diagnosis.html");
  await biRow.getByRole("button", { name: "面试", exact: true }).click();
  for (let index = 0; index < 6; index++) {
    await expect(page.locator(".interview-turn")).toHaveCount(index);
    await page.locator(".interview-panel textarea").fill("这是虚构候选人的演示回答，我使用Python、SQL和Excel处理10万条合成数据并制作8张图表，负责清洗、指标核对与数据可视化；尚未掌握Power BI，需要继续学习。所有项目和数字均为合成数据，不代表真实经历。");
    await page.getByRole("button", { name: "提交回答" }).click();
  }
  await expect(page.locator(".interview-turn")).toHaveCount(6);
  await expect(page.locator(".interview-summary")).toContainText("规则演示评分");
  const interviewDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载面试反馈 HTML" }).click();
  expect((await interviewDownload).suggestedFilename()).toBe("careerpilot-interview.html");
});

test("China demo loads on a phone without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "加载中国样例 · 合成简历" }).click();
  await expect(page.getByLabel("技能（可修改，逗号分隔）")).toHaveValue(/Python/);
  await page.getByRole("button", { name: "确认画像并进入岗位匹配" }).click();
  await expect(page.locator(".career-row")).toHaveCount(10);
  await expect(page.locator(".profile-analysis")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("real resume upload requires the data-processing acknowledgement", async ({ page, request }) => {
  await page.goto("/");
  const upload = page.getByRole("button", { name: "上传并解析" });
  await expect(upload).toBeDisabled();
  await page.getByRole("link", { name: "数据处理说明", exact: true }).click();
  await expect(page.getByRole("heading", { name: /你的简历如何被处理/ })).toBeVisible();
  await page.goto("/");
  const resume = await request.get("/api/v1/demo/china/resume");
  expect(resume.ok()).toBe(true);
  await page.locator("#resume").setInputFiles({
    name: "synthetic-resume.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: await resume.body(),
  });
  await page.getByRole("checkbox").check();
  await expect(upload).toBeEnabled();
  await upload.click();
  await expect(page.locator(".upload-section .notice.success")).toContainText("已接收");
});

test("a fresh browser establishes its session before delayed demo metadata and profile confirmation", async ({ page }) => {
  let releaseDemo!: () => void;
  let metadataStarted!: () => void;
  const metadataGate = new Promise<void>((resolve) => { releaseDemo = resolve; });
  const metadataRequest = new Promise<void>((resolve) => { metadataStarted = resolve; });
  let metadataCookie = "";
  await page.route("**/api/v1/demo/china", async (route) => {
    metadataCookie = route.request().headers().cookie ?? "";
    metadataStarted();
    await metadataGate;
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await metadataRequest;
  const start = page.getByRole("button", { name: "加载中国样例 · 合成简历" });
  try {
    expect(metadataCookie).toContain("careerpilot_session=");
    await expect(start).toBeDisabled();
  } finally {
    releaseDemo();
  }
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByLabel("技能（可修改，逗号分隔）")).toHaveValue(/Python/);
  const confirmed = page.waitForResponse((response) => response.url().includes("/profile/confirm") && response.request().method() === "POST");
  await page.getByRole("button", { name: "确认画像并进入岗位匹配" }).click();
  expect((await confirmed).ok()).toBe(true);
  await expect(page.getByRole("button", { name: "开始匹配" })).toBeVisible();
});


test("confirmed profile remains usable when career analysis fails and can be retried", async ({ page }) => {
  let analysisCalls = 0;
  await page.route("**/api/v1/resumes/*/analysis", async (route) => {
    analysisCalls += 1;
    if (analysisCalls === 1) {
      await route.fulfill({ status: 503, json: { detail: "职业分析暂时不可用，请重试。" } });
    } else {
      await route.continue();
    }
  });
  await page.goto("/");
  await page.getByRole("button", { name: "加载中国样例 · 合成简历" }).click();
  await page.getByRole("button", { name: "确认画像并进入岗位匹配" }).click();
  await expect(page.locator("#analysis").getByRole("alert")).toContainText("暂时不可用");
  await expect(page.getByRole("button", { name: "开始匹配" })).toBeVisible();
  await page.getByRole("button", { name: "重新加载分析" }).click();
  await expect(page.locator(".career-row")).toHaveCount(10);
  expect(analysisCalls).toBe(2);
});
