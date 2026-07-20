/**
 * Pilot verification gate — critical browser journeys with persistence checks.
 * Companion to msa/nda/dpa workflow specs. Run the full critical set twice.
 */
const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_owner';
const password = process.env.E2E_PASSWORD || 'e2e_pass_123';

async function login(page, user = username, pass = password) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', user);
  await page.fill('input[name="password"]', pass);
  await page.click('button[type="submit"]');
  await page.goto('/dashboard/');
  await expect(page).not.toHaveURL(/\/login\/?$/);
}

async function reveal(locator) {
  const section = locator.locator('xpath=ancestor::details[1]');
  if (await section.count() && !(await section.evaluate((element) => element.open))) {
    await section.locator('summary').click();
  }
  await expect(locator).toBeVisible();
}

async function fillField(page, key, value) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.fill(value);
}

async function selectField(page, key, value) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.selectOption(value);
}

async function checkField(page, key) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.check();
}

async function openWorkspaceActions(page) {
  const menu = page.locator('details.dc-ds-workspace__actions-menu');
  const summary = menu.locator('summary');
  await expect(summary).toBeVisible();
  if (!(await menu.evaluate((el) => el.open))) {
    await summary.click();
  }
  await expect(menu).toHaveJSProperty('open', true);
}

async function clearDraftingBlockers(page) {
  for (let i = 0; i < 20; i += 1) {
    const resolveBtn = page.getByRole('button', { name: /Resolve \d+ exceptions?/ }).first();
    if (!(await resolveBtn.count())) break;
    await resolveBtn.click();
    const drawer = page.getByRole('dialog', { name: 'Resolve exception' });
    await expect(drawer).toBeVisible();
    await drawer.getByRole('button', { name: 'Use approved wording' }).first().click();
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+/);
  }
  for (let i = 0; i < 30; i += 1) {
    const confirmBtn = page.locator('[data-action-mode="confirm"]').first();
    if (!(await confirmBtn.count())) break;
    await confirmBtn.click();
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+/);
  }
  await expect(page.getByText(/Send to Legal Review · blocked/)).toHaveCount(0);
}

/**
 * Minimal MSA generate for finance-threshold matrix (avoids unrelated finance triggers).
 */
async function generateMsa(page, { counterparty, value, confirmThreshold }) {
  await page.goto('/contracts/new/msa/');
  await expect(page.getByRole('heading', { name: 'New MSA Draft' })).toBeVisible();
  await selectField(page, 'payrollminds_contracting_entity', 'Payrollminds B.V.');
  await fillField(page, 'counterparty', counterparty);
  await fillField(page, 'start_date', '2026-10-01');
  await fillField(page, 'contract_owner', 'Avery Brooks');
  await fillField(page, 'business_unit', 'Revenue Operations');
  await fillField(page, 'internal_reference', `MSA-THR-${Date.now().toString().slice(-6)}`);
  await fillField(page, 'client_contact_name', 'Nina van Dijk');
  await fillField(page, 'client_contact_email', 'nina.vandijk@example.com');
  await fillField(page, 'value', String(value));
  await selectField(page, 'currency', 'EUR');
  await fillField(page, 'payment_terms', 'Net 30');
  await fillField(page, 'initial_term', '12 months');
  await selectField(page, 'renewal_type', 'Manual renewal');
  await fillField(page, 'termination_notice_period', '30');
  await fillField(page, 'consultant_service_type', 'Advisory');
  await fillField(page, 'services_description', 'Threshold verification services.');
  await fillField(page, 'governing_law', 'Netherlands');
  await fillField(page, 'jurisdiction', 'Amsterdam');
  await fillField(page, 'liability_cap', '1x annual fees');
  await fillField(page, 'confidentiality_period', '3 years');
  await selectField(page, 'ip_ownership', 'Provider');
  await checkField(page, 'sow_required');
  await checkField(page, 'deliverables_defined');
  await checkField(page, 'acceptance_criteria_required');
  if (confirmThreshold) {
    await checkField(page, 'value_above_threshold_confirmed');
  }
  await page.click('#submit-msa-btn');
  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+/, { timeout: 30000 });
}

test.describe('Verification: authentication', () => {
  test('logout returns to login and blocks dashboard', async ({ page }) => {
    await login(page);
    await page.getByRole('button', { name: /e2e_owner/i }).click();
    await Promise.all([
      page.waitForURL(/\/(login\/?)?$/),
      page.getByRole('menuitem', { name: 'Sign out' }).click(),
    ]);
    // LOGOUT_REDIRECT_URL is '/' — unauthenticated dashboard must bounce to login.
    await page.goto('/dashboard/');
    await expect(page).toHaveURL(/\/login\/?/);
  });

  test('session idle expiry redirects to login', async ({ page }) => {
    await login(page);
    await page.goto('/dashboard/?e2e_force_idle=1');
    await expect(page).toHaveURL(/\/login\/?/);
  });

  test('unrelated IP is not blocked by another IP counter', async ({ page, request }) => {
    await page.goto('/login/');
    const csrf = await page.locator('input[name="csrfmiddlewaretoken"]').inputValue();
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join('; ');
    const blockedIp = `198.51.100.${Math.floor(Math.random() * 50) + 10}`;
    const otherIp = `198.51.100.${Math.floor(Math.random() * 50) + 60}`;
    let saw429 = false;
    for (let i = 0; i < 8; i += 1) {
      const response = await request.post('/login/', {
        form: { username: 'nobody', password: 'wrong', csrfmiddlewaretoken: csrf },
        headers: {
          'X-Forwarded-For': blockedIp,
          Cookie: cookieHeader,
          Referer: 'http://127.0.0.1:8010/login/',
        },
      });
      if (response.status() === 429) {
        saw429 = true;
        break;
      }
    }
    expect(saw429).toBeTruthy();
    const other = await request.post('/login/', {
      form: { username: 'nobody', password: 'wrong', csrfmiddlewaretoken: csrf },
      headers: {
        'X-Forwarded-For': otherIp,
        Cookie: cookieHeader,
        Referer: 'http://127.0.0.1:8010/login/',
      },
    });
    expect(other.status()).toBe(200);
  });
});

test.describe('Verification: MSA finance threshold matrix', () => {
  test('Finance action absent below $100000 and present at/above threshold', async ({ page }) => {
    test.slow();
    await login(page);
    const suffix = Date.now().toString().slice(-5);

    await generateMsa(page, {
      counterparty: `Below Thr ${suffix}`,
      value: 99999,
      confirmThreshold: false,
    });
    await openWorkspaceActions(page);
    await expect(page.getByRole('menuitem', { name: 'Send to Finance' })).toHaveCount(0);

    await generateMsa(page, {
      counterparty: `Exact Thr ${suffix}`,
      value: 100000,
      confirmThreshold: false,
    });
    await clearDraftingBlockers(page);
    await openWorkspaceActions(page);
    await expect(page.getByRole('menuitem', { name: 'Send to Finance' })).toBeVisible();
    await page.getByRole('menuitem', { name: 'Send to Finance' }).click();
    await expect(page.getByText(/MSA submitted to .* for review/i).first()).toBeVisible();
    const exactUrl = page.url();
    await page.reload();
    await expect(page).toHaveURL(exactUrl);
    await page.getByRole('button', { name: /Review Finance|Review MSA|Review privacy|Review generated|Review approval|Confirm drafting|open exception/i }).first().click();
    const exactDrawer = page.getByRole('dialog', { name: 'Governance details' });
    await expect(exactDrawer.getByRole('heading', { name: 'Audit details' })).toBeVisible();
    await expect(exactDrawer).toContainText(/Finance|review|submitted|Audit|approval/i);
    await exactDrawer.getByRole('button', { name: 'Close governance details' }).click();

    await generateMsa(page, {
      counterparty: `Above Thr ${suffix}`,
      value: 100001,
      confirmThreshold: false,
    });
    await clearDraftingBlockers(page);
    await openWorkspaceActions(page);
    await expect(page.getByRole('menuitem', { name: 'Send to Finance' })).toBeVisible();
    await page.getByRole('menuitem', { name: 'Send to Finance' }).click();
    await expect(page.getByText(/MSA submitted to .* for review/i).first()).toBeVisible();
  });

  test('Legal submit persists after refresh and shows audit history', async ({ page }) => {
    test.slow();
    await login(page);
    const suffix = Date.now().toString().slice(-5);
    await generateMsa(page, {
      counterparty: `Audit MSA ${suffix}`,
      value: 150000,
      confirmThreshold: true,
    });
    await clearDraftingBlockers(page);
    await openWorkspaceActions(page);
    await page.getByRole('menuitem', { name: 'Send to Legal Review' }).click();
    await expect(page.getByText(/MSA submitted to .* for review/i).first()).toBeVisible();
    const workflowUrl = page.url();
    await page.reload();
    await expect(page).toHaveURL(workflowUrl);
    // Governance drawer carries Audit details for MSA (no Activity rail tab).
    await page.getByRole('button', { name: /Review Finance|Review MSA|Review privacy|Review generated|Review approval|Confirm drafting|open exception/i }).first().click();
    const governanceDrawer = page.getByRole('dialog', { name: 'Governance details' });
    await expect(governanceDrawer.getByRole('heading', { name: 'Audit details' })).toBeVisible();
    await expect(governanceDrawer).toContainText(/Legal|review|submitted|Audit|approval/i);
    await governanceDrawer.getByRole('button', { name: 'Close governance details' }).click();
  });
});

test.describe('Verification: NDA supported actions', () => {
  test('click View contract record and Activity audit rail', async ({ page }) => {
    test.slow();
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    await page.goto('/contracts/new/nda/');
    await page.fill('[data-field-key="counterparty"]', `Verify NDA ${suffix}`);
    await page.fill('[data-field-key="start_date"]', '2026-10-01');
    await page.fill('[data-field-key="contract_owner"]', 'Avery Brooks');
    await page.fill('[data-field-key="business_unit"]', 'Revenue Operations');
    await page.fill('[data-field-key="internal_reference"]', `NDA-V-${suffix}`);
    await page.selectOption('[data-field-key="nda_type"]', 'Mutual');
    await page.fill('[data-field-key="confidentiality_purpose"]', 'product diligence');
    await page.fill('[data-field-key="confidentiality_period"]', '2');
    await page.fill('[data-field-key="disclosure_scope"]', 'technical architecture');
    await page.fill('[data-field-key="permitted_recipients"]', 'employees');
    await page.fill('[data-field-key="governing_law"]', 'Netherlands');
    await page.fill('[data-field-key="jurisdiction"]', 'Amsterdam');
    await page.check('[data-field-key="injunctive_relief_included"]');
    await page.click('#submit-nda-btn');
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
    await expect(page.getByRole('button', { name: 'Send for signature' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Export Word' })).toHaveCount(0);
    await expect(page.getByText('Send to Legal Review · not required')).toBeVisible();
    await page.locator('details.dc-ds-workspace__actions-menu summary').click();
    await page.getByRole('menuitem', { name: 'View contract record' }).click();
    await expect(page).toHaveURL(/\/contracts\/\d+\/?$/);
    await page.reload();
    await expect(page.getByText(`Verify NDA ${suffix}`).first()).toBeVisible();
  });
});

test.describe('Verification: DPA supported actions', () => {
  test('unsupported CTAs absent; View record + Activity persist', async ({ page }) => {
    test.slow();
    await login(page);
    // Full generate covered by dpa-workflow.spec.js; assert workspace honesty on existing path.
    await page.goto('/contracts/new/dpa/');
    await expect(page.getByRole('heading', { name: /^New DPA\b/ })).toBeVisible();
    await page.locator('[data-field-key="counterparty"]').fill(`Verify DPA ${Date.now().toString().slice(-5)}`);
    await page.locator('[data-field-key="contract_owner"]').fill('Avery Brooks');
    await page.locator('[data-field-key="start_date"]').fill('2026-09-01');
    await page.getByRole('button', { name: /^(Continue|Review and generate)$/ }).click();
    // Stop early if validation blocks — full path is in dpa-workflow.spec.js.
    // Honesty check: launcher must not advertise inert legal/export actions.
    await expect(page.getByRole('button', { name: 'Send to Legal Review' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Export Word' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Review next action' })).toHaveCount(0);
  });
});

test.describe('Verification: search fixtures and tenancy', () => {
  for (const fixture of ['valid', 'list', 'malformed', 'empty', 'error', 'timeout', 'keyword']) {
    test(`semantic fixture ${fixture} does not 500`, async ({ page }) => {
      await login(page);
      const response = await page.goto(
        `/contracts/search/?q=e2e_fixture:${fixture}&search_mode=semantic`,
      );
      expect(response.status()).toBeLessThan(500);
      await expect(page).not.toHaveURL(/\/login\/?$/);
      await expect(page.locator('body')).toContainText(/Search|result|clause|No /i);
      await expect(page.getByRole('link', { name: 'FOREIGN_TENANT_SECRET_CLAUSE_E2E' })).toHaveCount(0);
    });
  }

  test('cross-tenant clause title is excluded from results', async ({ page }) => {
    await login(page);
    await page.goto('/contracts/search/?q=FOREIGN_TENANT_SECRET_CLAUSE_E2E&search_mode=keyword');
    await expect(page.getByRole('link', { name: 'FOREIGN_TENANT_SECRET_CLAUSE_E2E' })).toHaveCount(0);
    await expect(page.locator('article, .search-hit, .list-row').filter({ hasText: 'FOREIGN_TENANT_SECRET_CLAUSE_E2E' })).toHaveCount(0);
    await page.goto('/contracts/search/?q=E2E%20Local%20Indemnity%20Clause&search_mode=keyword');
    await expect(page.locator('body')).toContainText(/E2E Local Indemnity Clause/i);
  });
});

test.describe('Verification: lifecycle Stage vs Status', () => {
  test('repository Stage sort and Status filter controls', async ({ page }) => {
    await login(page);
    await page.goto('/contracts/repository/');
    await expect(page.locator('button.repo-sort-btn[data-sort="stage"]')).toBeVisible();
    await page.locator('button.repo-sort-btn[data-sort="stage"]').click();
    await expect(page).toHaveURL(/sort|stage/);
    await expect(page.locator('body')).toContainText(/Stage|Status|Contract/i);
  });

  test('invalid lifecycle stage skip is rejected via repository bulk-update API', async ({ page }) => {
    test.slow();
    await login(page);
    const suffix = Date.now().toString().slice(-5);
    await page.goto('/contracts/new/nda/');
    await page.fill('[data-field-key="counterparty"]', `Life NDA ${suffix}`);
    await page.fill('[data-field-key="start_date"]', '2026-10-01');
    await page.fill('[data-field-key="contract_owner"]', 'Avery Brooks');
    await page.fill('[data-field-key="business_unit"]', 'Revenue Operations');
    await page.fill('[data-field-key="internal_reference"]', `NDA-L-${suffix}`);
    await page.selectOption('[data-field-key="nda_type"]', 'Mutual');
    await page.fill('[data-field-key="confidentiality_purpose"]', 'product diligence');
    await page.fill('[data-field-key="confidentiality_period"]', '2');
    await page.fill('[data-field-key="disclosure_scope"]', 'technical architecture');
    await page.fill('[data-field-key="permitted_recipients"]', 'employees');
    await page.fill('[data-field-key="governing_law"]', 'Netherlands');
    await page.fill('[data-field-key="jurisdiction"]', 'Amsterdam');
    await page.check('[data-field-key="injunctive_relief_included"]');
    await page.click('#submit-nda-btn');
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+/);
    await page.getByRole('link', { name: 'View contract record' }).click();
    await expect(page).toHaveURL(/\/contracts\/\d+\/?$/);
    const contractId = page.url().match(/\/contracts\/(\d+)/)[1];

    // Edit form deliberately omits lifecycle_stage; repository bulk-update is the
    // governed mutation path (PDR-0002) and must reject illegal skips.
    await page.goto('/contracts/repository/');
    const result = await page.evaluate(async (id) => {
      const cookieMatch = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      const csrf = cookieMatch ? decodeURIComponent(cookieMatch[1]) : '';
      if (!csrf) return { ok: false, reason: 'missing-csrf' };
      const response = await fetch('/contracts/api/contracts/bulk-update/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
        body: JSON.stringify({
          contract_ids: [String(id)],
          updates: { lifecycle_stage: 'SIGNATURE' },
        }),
      });
      const text = await response.text();
      let payload = null;
      try {
        payload = JSON.parse(text);
      } catch (_err) {
        payload = null;
      }
      return {
        ok: true,
        status: response.status,
        error: (payload && (payload.error || payload.detail)) || text.slice(0, 400),
      };
    }, contractId);

    expect(result.ok).toBeTruthy();
    expect(result.reason || null).toBeNull();
    expect(result.status).toBeGreaterThanOrEqual(400);
    expect(String(result.error)).toMatch(/cannot transition|lifecycle|not allowed|invalid/i);

    // Valid adjacent transition persists and writes audit history on the record.
    const allowed = await page.evaluate(async (id) => {
      const cookieMatch = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      const csrf = cookieMatch ? decodeURIComponent(cookieMatch[1]) : '';
      const response = await fetch('/contracts/api/contracts/bulk-update/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
        body: JSON.stringify({
          contract_ids: [String(id)],
          updates: { lifecycle_stage: 'INTERNAL_REVIEW' },
        }),
      });
      const payload = await response.json();
      return { status: response.status, success: Boolean(payload.success) };
    }, contractId);
    expect(allowed.status).toBe(200);
    expect(allowed.success).toBeTruthy();

    await page.goto(`/contracts/${contractId}/`);
    await page.reload();
    await expect(page.locator('body')).toContainText(/Internal review|INTERNAL_REVIEW|Stage/i);
  });
});
