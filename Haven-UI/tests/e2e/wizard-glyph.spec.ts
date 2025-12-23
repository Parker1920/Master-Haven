import { test, expect } from '@playwright/test';

test.describe('Wizard glyph behavior', () => {
  test('clicking glyphs should not submit the form', async ({ page }) => {
    await page.goto('/#/wizard');

    page.on('request', req => {
      const url = String(req.url());
      if (url.includes('/api/submit_system') || url.includes('/api/save_system')) {
        throw new Error('Clicking glyphs should not trigger submit_system or save_system POST');
      }
    });

    await page.waitForSelector('button:has-text("0")');
    await page.click('button:has-text("0")');
    await page.waitForTimeout(150);
    await page.click('button:has-text("1")');

    // Ensure no submission fired
    await page.waitForTimeout(500);

    // Glyph code should be updated
    const codeCount = await page.locator('.glyph-picker .font-mono').count();
    expect(codeCount).toBeGreaterThan(0);
  });
});
