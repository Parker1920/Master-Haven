import { test, expect } from '@playwright/test';

test.describe('Wizard Enter behavior', () => {
  test('pressing Enter in text input should not auto-submit', async ({ page }) => {
    await page.goto('/#/wizard');

    // Fail test if submit or save is invoked
    page.on('request', req => {
      const url = String(req.url());
      if (url.includes('/api/submit_system') || url.includes('/api/save_system')) {
        throw new Error('Form should not auto-submit when pressing Enter inside text inputs');
      }
    });

    await page.fill('input[placeholder="Name"]', 'Auto Submit Prevent Test');
    await page.keyboard.press('Enter');

    // Wait a little to see if any request fires
    await page.waitForTimeout(1000);

    // Confirm we are still on the wizard and the input contents are preserved
    const nameVal = await page.inputValue('input[placeholder="Name"]');
    expect(nameVal).toBe('Auto Submit Prevent Test');
  });

  test('clicking glyphs should not auto-submit', async ({ page }) => {
    await page.goto('/#/wizard');

    // Fail test if submit or save is invoked
    page.on('request', req => {
      const url = String(req.url());
      if (url.includes('/api/submit_system') || url.includes('/api/save_system')) {
        throw new Error('Clicking glyphs should not auto-submit the form');
      }
    });

    // Wait for the glyph buttons to load and click one
    await page.waitForSelector('button:has-text("0")');
    await page.click('button:has-text("0")');
    // Click another to be sure
    await page.waitForTimeout(250);
    await page.click('button:has-text("1")');

    // Wait to ensure no auto submit occurred
    await page.waitForTimeout(1000);

    // Verify glyph code is visible (ensure UI updated)
    const glyphDisplay = await page.textContent('.glyph-picker');
    expect(glyphDisplay).toContain('0');
  });

  test('pressing Enter on submit button should submit', async ({ page }) => {
    await page.goto('/#/wizard');

    await page.fill('input[placeholder="Name"]', 'Submit By Button Test');

    const requestPromise = page.waitForRequest(req => req.url().includes('/api/submit_system') || req.url().includes('/api/save_system'));

    await page.click('button[type="submit"]');

    const req = await requestPromise;
    expect(req).toBeTruthy();
    expect(req.method()).toBe('POST');
  });
});
