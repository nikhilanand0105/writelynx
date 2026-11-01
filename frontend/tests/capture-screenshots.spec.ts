import { test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const SCREENSHOTS_DIR = path.resolve(process.cwd(), 'docs/screenshots');

test.describe('Capture Writelynx Workflow Screenshots', () => {

  test('Capture key student workflow states', async ({ page, context }) => {
    // 1. Authenticate a returning test student
    const studentEmail = '21bce1001@vitstudent.ac.in';
    const resp = await page.request.post('http://127.0.0.1:8000/api/auth/google-login', {
      data: { id_token: `mock-token:${studentEmail}` },
    });
    const authData = await resp.json();

    await context.addCookies([
      { name: 'writelynx_session', value: authData.token, domain: 'localhost', path: '/' },
    ]);

    // State 1: Returning Student Home
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '01_homepage_returning.png'), fullPage: true });

    // State 2: My Documents Page
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '02_my_documents.png'), fullPage: true });

    // State 3: New Document Wizard - Step 1: Help Mode
    await page.goto('/documents/new');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '03_wizard_help_mode.png'), fullPage: true });

    // State 4: New Document Wizard - Step 2: Choose Plan
    await page.locator('text=Continue to Plan Selection').click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '04_wizard_choose_plan.png'), fullPage: true });

    // State 5: Document Workspace - Review View
    await page.goto('/documents');
    const openBtn = page.locator('button:has-text("Open Workspace")').first();
    if (await openBtn.isVisible().catch(() => false)) {
      await openBtn.click();
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '05_workspace_review.png'), fullPage: true });

      // State 6: Document Workspace - Sources & Checks View
      await page.locator('button:has-text("Sources & Checks")').first().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '06_workspace_sources_checks.png'), fullPage: true });

      // State 7: Document Workspace - History View
      await page.locator('button:has-text("History")').first().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '07_workspace_history.png'), fullPage: true });
    }

    // State 8: Student Account Page
    await page.goto('/account');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '08_account_page.png'), fullPage: true });

    // State 9: First-Time Student Home (0 documents)
    const freshEmail = `21bcez${Math.floor(1000 + Math.random() * 9000)}@vitstudent.ac.in`;
    const freshResp = await page.request.post('http://127.0.0.1:8000/api/auth/google-login', {
      data: { id_token: `mock-token:${freshEmail}` },
    });
    const freshData = await freshResp.json();
    await context.clearCookies();
    await context.addCookies([
      { name: 'writelynx_session', value: freshData.token, domain: 'localhost', path: '/' },
    ]);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '09_homepage_first_time.png'), fullPage: true });

    // State 10: Mobile Viewport (iPhone 12, 390x844)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '10_mobile_home.png'), fullPage: true });
  });

});
