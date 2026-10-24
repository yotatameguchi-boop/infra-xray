import { test, expect } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
let processHandle: ChildProcess, url: string;
async function launch(file: string) {
  const child = spawn(
    "python3",
    [
      "-m",
      "infra_xray",
      "view",
      `examples/synthetic-plans/${file}`,
      "--no-open",
    ],
    { cwd: ".." },
  );
  const address = await new Promise<string>((resolve, reject) => {
    let out = "";
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error("CLI startup timeout"));
    }, 10000);
    child.stdout?.on("data", (d) => {
      out += d.toString();
      const m = out.match(/http:\/\/127\.0\.0\.1:\d+\/#token=[\w-]+/);
      if (m) {
        clearTimeout(timeout);
        resolve(m[0]);
      }
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      clearTimeout(timeout);
      reject(new Error("CLI exited " + code));
    });
  });
  return { child, address };
}
test.beforeAll(async () => {
  const s = await launch("review.json");
  processHandle = s.child;
  url = s.address;
});
test.afterAll(() => processHandle?.kill());
test("local explorer: views, inspection, search, keyboard, findings and responsive layout", async ({
  page,
}) => {
  const errors: string[] = [];
  const external: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (!r.url().startsWith("http://127.0.0.1:")) external.push(r.url());
  });
  await page.goto(url);
  await expect(
    page.getByRole("heading", { name: "Infrastructure explorer." }),
  ).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(9);
  await expect(page.locator(".finding-row")).toHaveCount(3);
  await expect(page.locator(".react-flow__edge")).toHaveCount(10);
  await page.getByRole("tab", { name: "Changes" }).click();
  await expect(page.getByRole("tab", { name: "Changes" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.locator('[data-id="aws_db_instance.primary"]').click();
  await expect(page.locator(".details h2")).toHaveText("primary");
  await expect(page.locator(".details .badge")).toContainText("Replace");
  await expect(page.locator(".details")).toContainText("DB-001");
  await page.getByLabel("リソース検索").fill("application");
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.getByLabel("検索をクリア").click();
  await expect(page.locator(".react-flow__node")).toHaveCount(9);
  await page.getByRole("tab", { name: "Security" }).click();
  await expect(page.locator(".resource-node.risk")).toHaveCount(2);
  await page.locator(".finding-row").filter({ hasText: "SG-001" }).click();
  await expect(page.locator(".details h2")).toHaveText("web_access");
  await expect(page.locator(".details")).toContainText("判定根拠");
  await page.getByRole("button", { name: "詳細を閉じる" }).click();
  await expect(page.getByText("A closer look")).toBeVisible();
  await page.getByRole("tab", { name: "Architecture", exact: true }).click();
  await page.getByRole("button", { name: "グラフ全体を表示" }).click();
  await page.waitForTimeout(450);
  await mkdir("../docs/screenshots", { recursive: true });
  await page.screenshot({
    path: "../docs/screenshots/desktop.png",
    fullPage: true,
  });
  const target = page.locator('[data-id="aws_db_instance.primary"]');
  await target.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".details h2")).toHaveText("primary");
  await page.getByRole("button", { name: "診断の範囲と限界" }).click();
  await expect(page.locator(".help-panel")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../docs/screenshots/mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
  await page.reload();
  await expect(page.locator(".react-flow__node")).toHaveCount(9);
});
test("100 resources render locally", async ({ page }) => {
  const s = await launch("100-resources.json");
  try {
    const start = Date.now();
    await page.goto(s.address);
    await expect(page.locator(".react-flow__node")).toHaveCount(100);
    const ms = Date.now() - start;
    await writeFile(
      "../docs/browser-performance.json",
      JSON.stringify(
        {
          resources: 100,
          readyMs: ms,
          viewport: "1440x1050",
          browser: "Chromium / Playwright",
          note: "One local run; navigation to 100 mounted nodes, not a general performance guarantee.",
        },
        null,
        2,
      ),
    );
  } finally {
    s.child.kill();
  }
});
