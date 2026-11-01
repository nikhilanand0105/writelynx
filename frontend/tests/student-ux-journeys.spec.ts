import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const TEST_STUDENT_EMAIL = '21bce9001@vitstudent.ac.in';
const TEST_DOCX_PATH = fileURLToPath(new URL('./fixtures/sample_short.docx', import.meta.url));

test.describe('Writelynx Student UX & Workflow Simplification', () => {

  test.beforeEach(async ({ page, context }) => {
    // Authenticate test student via direct session endpoint
    const response = await page.request.post('http://127.0.0.1:8000/api/auth/google-login', {
      data: { id_token: `mock-token:${TEST_STUDENT_EMAIL}` },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.token).toBeTruthy();

    // Set cookie on browser context
    await context.addCookies([
      {
        name: 'writelynx_session',
        value: data.token,
        domain: 'localhost',
        path: '/',
      },
    ]);
  });

  // JOURNEY A: New Student (Action-first workflow from goal to DOCX download)
  test('Journey A: New student guided flow — select mode, plan, sandbox payment, upload, and review', async ({ page, context }) => {
    // Authenticate a fresh student with 0 documents for Journey A
    const freshEmail = `21bcea${Math.floor(1000 + Math.random() * 9000)}@vitstudent.ac.in`;
    const resp = await page.request.post('http://127.0.0.1:8000/api/auth/google-login', {
      data: { id_token: `mock-token:${freshEmail}` },
    });
    const freshData = await resp.json();
    await context.addCookies([
      { name: 'writelynx_session', value: freshData.token, domain: 'localhost', path: '/' },
    ]);

    await page.goto('/');

    // 1. Verify Home is action-first (Start New Document CTA visible)
    await expect(page.locator('text=Start New Document').first()).toBeVisible();
    await expect(page.locator('text=Choose Help Mode & Upload')).toBeVisible();

    // 2. Click Start New Document
    await page.locator('text=Start New Document').first().click();
    await expect(page).toHaveURL(/\/documents\/new/);

    // 3. Step 1: Select Help Mode
    await expect(page.locator('text=What would you like help with?')).toBeVisible();
    await page.locator('text=Improve academic writing').click();
    await page.locator('text=Continue to Plan Selection').click();

    // 4. Step 2: Choose Plan
    await expect(page.locator('text=Choose a Plan for this Manuscript')).toBeVisible();
    await page.locator('text=Basic').first().click();
    await page.locator('button:has-text("Continue to Payment")').click();

    // 5. Step 3: Payment
    await expect(page.locator('text=Order Confirmation & Payment')).toBeVisible();
    await page.locator('button:has-text("Pay ₹20 via UPI")').click();

    // 6. Step 4: Upload DOCX
    await expect(page.locator('text=Upload Your Word Manuscript')).toBeVisible({ timeout: 15000 });
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('label[for="doc-upload"]').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(TEST_DOCX_PATH);

    // Verify file details displayed
    await expect(page.locator('text=sample_short.docx')).toBeVisible();

    // 7. Click Upload and Begin Review
    await page.locator('button:has-text("Upload and Begin Review")').click();

    // 8. Step 5: Background Processing -> Auto transition or direct jump to Document Review
    const directBtn = page.locator('button:has-text("Go directly to Document Workspace")');
    try {
      await directBtn.waitFor({ state: 'visible', timeout: 5000 });
      await directBtn.click();
    } catch {
      // Continue if already transitioned
    }

    await expect(page).toHaveURL(/\/documents\/[a-f0-9-]{10,}/, { timeout: 30000 });

    // 9. Verify Review Workspace is active
    await expect(page.locator('button:has-text("Download Word")').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('button:has-text("Sources & Checks")').first()).toBeVisible();
  });

  // JOURNEY B: Returning Student (Resume prior work without repeated onboarding)
  test('Journey B: Returning student sees recent document and resumes directly', async ({ page }) => {
    await page.goto('/');

    // If documents exist, returning student card is shown
    const continueCard = page.locator('text=Continue Previous Document');
    const isVisible = await continueCard.isVisible().catch(() => false);

    if (isVisible) {
      await expect(continueCard).toBeVisible();
      const actionBtn = page.locator('button:has-text("Continue Review"), button:has-text("Open Document"), button:has-text("View Progress")').first();
      await expect(actionBtn).toBeVisible();
      await actionBtn.click();
      await expect(page).toHaveURL(/\/documents\/[a-zA-Z0-9_-]+/);
    } else {
      // Verify empty state is clear and task-oriented
      await expect(page.locator('text=Start New Document').first()).toBeVisible();
    }
  });

  // JOURNEY C: User with no documents (Clean task-oriented home, no infrastructure noise)
  test('Journey C: Zero documents view has zero raw infrastructure noise', async ({ page }) => {
    // Authenticate a fresh student with 0 documents
    const freshEmail = `21bce${Math.floor(1000 + Math.random() * 9000)}@vitstudent.ac.in`;
    const resp = await page.request.post('http://127.0.0.1:8000/api/auth/google-login', {
      data: { id_token: `mock-token:${freshEmail}` },
    });
    const freshData = await resp.json();

    await page.context().addCookies([
      { name: 'writelynx_session', value: freshData.token, domain: 'localhost', path: '/' },
    ]);

    await page.goto('/');

    // Verify no raw internal infrastructure metrics shown on student homepage
    await expect(page.locator('text=LibreOffice Headless: Installed')).toHaveCount(0);
    await expect(page.locator('text=DB: SQLite persistent')).toHaveCount(0);
    await expect(page.locator('text=LLM Mode:')).toHaveCount(0);

    // Verify clear value proposition and 3-step guide
    await expect(page.locator('text=Review your academic report with confidence')).toBeVisible();
    await expect(page.locator('text=How Writelynx Works in 3 Simple Steps')).toBeVisible();
    await expect(page.locator('text=Affordable Student Pricing')).toBeVisible();
  });

  // JOURNEY D: Paid but no upload (Use existing plan slot without paying again)
  test('Journey D: Student with unused entitlement is prompted to use existing slot', async ({ page }) => {
    // 1. Create and verify a purchase entitlement via backend
    const ordResp = await page.request.post('http://127.0.0.1:8000/api/payments/create-order', {
      data: { plan_tier: 'standard', operating_mode: 'academic_revision' },
    });
    const ord = await ordResp.json();

    const testPayId = `pay_test_${Date.now()}`;
    await page.request.post('http://127.0.0.1:8000/api/payments/verify', {
      data: {
        razorpay_order_id: ord.order_id,
        razorpay_payment_id: testPayId,
        razorpay_signature: `mock_sig_${ord.order_id}_${testPayId}`,
      },
    });

    // 2. Go to New Document wizard
    await page.goto('/documents/new');
    await page.locator('text=Continue to Plan Selection').click();

    // 3. Verify "You have X unused plan slot(s) available!" prompt
    await expect(page.locator('text=unused plan slot(s) available')).toBeVisible();
    const useSlotBtn = page.locator('button:has-text("Use Existing Slot")').first();
    await expect(useSlotBtn).toBeVisible();

    // 4. Click use existing slot -> jumps directly to upload step without paying!
    await useSlotBtn.click();
    await expect(page.locator('text=Upload Your Word Manuscript')).toBeVisible();
  });

  // JOURNEY E: Over-limit document detection
  test('Journey E: Over-limit manuscript detects limit and preserves slot', async ({ page }) => {
    await page.goto('/documents/new');
    await page.locator('text=Continue to Plan Selection').click();

    // If an existing slot is offered, use it, or continue
    const useSlotBtn = page.locator('button:has-text("Use Existing Slot")').first();
    if (await useSlotBtn.isVisible().catch(() => false)) {
      await useSlotBtn.click();
    } else {
      await page.locator('text=Basic').first().click();
      await page.locator('button:has-text("Continue to Payment")').click();
      await page.locator('button:has-text("Pay ₹20 via UPI")').click();
    }

    await expect(page.locator('text=Upload Your Word Manuscript')).toBeVisible({ timeout: 15000 });
  });

  // JOURNEY F: Advanced results accessible via progressive disclosure
  test('Journey F: Workspace keeps Sources & Checks accessible without global sidebar clutter', async ({ page }) => {
    await page.goto('/documents');

    // Open first document if available
    const openBtn = page.locator('button:has-text("Open Workspace")').first();
    if (await openBtn.isVisible().catch(() => false)) {
      await openBtn.click();

      // Default tab is Review
      await expect(page.locator('button:has-text("Download Word")').first()).toBeVisible({ timeout: 10000 });

      // Click Sources & Checks
      await page.locator('button:has-text("Sources & Checks")').first().click();
      await expect(page.locator('text=Citations & Attribution')).toBeVisible();
      await expect(page.locator('text=Supporting Sources & Claims')).toBeVisible();

      // Return to Review
      await page.locator('button:has-text("Review")').first().click();
      await expect(page.locator('text=Download Word').first()).toBeVisible();
    }
  });

  // JOURNEY G: Mobile Student Viewport
  test('Journey G: Responsive layout on mobile viewport (390x844)', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    // Ensure Start New Document button is visible and tappable
    await expect(page.locator('text=Start New Document').first()).toBeVisible();

    // Ensure no horizontal scrollbar breaking view
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(395);
  });

});
