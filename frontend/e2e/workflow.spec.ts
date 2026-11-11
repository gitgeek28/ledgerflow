import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page, name = "Aisha Rao") {
  await page.goto("/login");
  await page.getByRole("radio", { name: new RegExp(name) }).click();
  await page.getByLabel("Demo password").fill("ledgerflow-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
}

test("upload → live run → evidence → human review → audit", async ({ page }) => {
  await signIn(page);
  await expect(page.getByText("Touchless rate")).toBeVisible();

  await page.getByRole("link", { name: "Upload invoices" }).click();
  await page.getByRole("button", { name: "Upload sample S09" }).click();

  // Live run view driven by SSE events persisted by the backend
  await page.waitForURL(/\/runs\//);
  await expect(page.getByText("Workflow stages")).toBeVisible();
  await expect(page.getByText("PO-450109 matched by reference")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision" })).toBeVisible();
  await expect(page.getByText(/Unit price variance above tolerance \(line 1: 43,500.00 vs 42,000.00\)/).first()).toBeVisible();

  // Investigation: reconciliation evidence
  await page.getByRole("link", { name: "Review evidence and checks" }).click();
  await page.getByRole("tab", { name: "Reconciliation" }).click();
  await expect(page.getByText("+3.57%").first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "+2.00%" }).first()).toBeVisible();

  // Human action with mandatory reason
  await page.getByRole("button", { name: "Hold" }).click();
  const confirm = page.getByRole("dialog").getByRole("button", { name: "Place on hold" });
  await expect(confirm).toBeDisabled();
  await page.getByLabel(/Reason/).fill("Waiting for buyer to confirm the revised licence price");
  await confirm.click();
  await expect(page.getByText("On hold").first()).toBeVisible();

  // Audit trail distinguishes the human action from the system decision
  await page.getByRole("tab", { name: "Activity & audit" }).click();
  await expect(page.getByText("Waiting for buyer to confirm the revised licence price").first()).toBeVisible();
  await expect(page.getByText("System decision").first()).toBeVisible();
});

test("exact duplicate file is linked, not re-processed", async ({ page }) => {
  await signIn(page);
  await page.goto("/invoices/new");
  await page.getByRole("button", { name: "Upload sample S01" }).click();
  await page.waitForURL(/\/runs\//);
  await page.goto("/invoices/new");
  await page.getByRole("button", { name: "Upload sample S02" }).click();
  await expect(page.getByText("Exact duplicate file", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/No new invoice was created/)).toBeVisible();
});

test("auditor is read-only and theme toggles to dark", async ({ page }) => {
  await signIn(page, "Meera Joshi");
  await expect(page.getByRole("link", { name: "Upload invoices" })).toHaveCount(0);
  await page.getByRole("button", { name: "Toggle colour theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
});
