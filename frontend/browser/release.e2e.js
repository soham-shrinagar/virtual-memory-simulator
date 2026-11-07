import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test.beforeEach(async ({ page, context, baseURL }) => {
  await context.route('**/*', (route) =>
    new URL(route.request().url()).origin === baseURL ? route.continue() : route.abort(),
  );
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Virtual memory', exact: true })).toBeVisible();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
});

test('replays address translation and restores a downloaded experiment', async ({ page }) => {
  await page.getByLabel('Reference type').selectOption('addresses');
  await page.getByLabel('Replacement policy').selectOption('clock');
  await page.getByLabel('Translation cache (TLB)').selectOption('2');
  const references = page.getByLabel('Memory references');
  await references.fill('4096, 8300, 4097');
  const run = page.getByRole('button', { name: 'Run simulation' });
  await run.click();
  const step = page.getByLabel('Current step');
  await expect(step).toHaveText('0 / 3');

  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await page.getByLabel('Simulation step').press('ArrowRight');
  await expect(step).toHaveText('2 / 3');
  await expect(page.getByLabel('Offset', { exact: true })).toHaveText('108');
  await expect(page.getByLabel('Physical address', { exact: true })).toHaveText('4,204');
  await page.getByRole('button', { name: 'Previous', exact: true }).click();
  await expect(step).toHaveText('1 / 3');
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(step).toHaveText('0 / 3');
  await page.getByLabel('Playback speed').selectOption('200');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect(step).toHaveText('3 / 3');
  await expect(page.getByLabel('Faults', { exact: true })).toHaveText('2');
  await expect(page.getByRole('region', { name: 'Policy state' })).toContainText('CLOCK');
  await expect(page.getByRole('region', { name: 'Translation cache', exact: true })).toContainText('Cache hits: 1 · misses: 2');

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Save JSON' }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('experiment.json');
  const file = await download.path();
  expect(JSON.parse(await readFile(file, 'utf8'))).toMatchObject({
    schema_version: 3, workload: [4096, 8300, 4097], operations: ['read', 'read', 'read'],
    input_mode: 'addresses', policy: 'clock', tlb_capacity: 2,
  });

  await page.getByLabel('Reference type').selectOption('pages');
  await page.getByLabel('Replacement policy').selectOption('fifo');
  await page.getByLabel('Translation cache (TLB)').selectOption('0');
  await references.fill('0');
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.getByRole('button', { name: 'Load JSON' }).click(),
  ]);
  await chooser.setFiles({ name: 'experiment.json', mimeType: 'application/json', buffer: await readFile(file) });
  await expect(references).toHaveValue('4096, 8300, 4097');
  await expect(page.getByLabel('Reference type')).toHaveValue('addresses');
  await expect(page.getByLabel('Replacement policy')).toHaveValue('clock');
  await expect(page.getByLabel('Translation cache (TLB)')).toHaveValue('2');
  await run.click();
  await expect(step).toHaveText('0 / 3');
});

test('generates references and exports a Belady sweep at a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByText('Generate references', { exact: true }).click();
  await page.getByLabel('Workload profile').selectOption('sequential');
  await page.getByLabel('Seed', { exact: true }).fill('42');
  await page.getByLabel('Reference count').fill('4');
  await page.getByRole('button', { name: 'Generate workload' }).click();
  await expect(page.getByLabel('Memory references')).toHaveValue('5, 6, 7, 0');

  await page.getByRole('button', { name: 'compare view' }).click();
  await page.getByRole('button', { name: 'Belady preset' }).click();
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  await expect(page.getByText(/Belady’s anomaly observed/)).toContainText('3 → 4 frames: 9 → 10 faults');
  await expect(page.getByRole('table', { name: 'Comparison results' }).getByRole('row')).toHaveCount(9);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('comparison.csv');
  const [header, ...rows] = (await readFile(await download.path(), 'utf8')).trimEnd().split(/\r?\n/);
  expect(header.split(',').slice(0, 5)).toEqual(['policy', 'physical_frames', 'references', 'hits', 'faults']);
  expect(rows).toHaveLength(8);
  expect(rows.filter((row) => row.startsWith('fifo,')).map((row) => row.split(',').slice(1, 5))).toEqual([
    ['3', '12', '3', '9'],
    ['4', '12', '2', '10'],
  ]);
});

test('restores dirty state and writebacks and saves mixed read/write references', async ({ page }) => {
  await page.getByLabel('Physical frames').fill('1');
  await page.getByLabel('Translation cache (TLB)').selectOption('2');
  await page.getByLabel('Memory references').fill('W:0 R:0 1 0 W:0 W:0 2');
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByLabel('Current step')).toHaveText('0 / 7');
  const timeline = page.getByLabel('Simulation step');
  await timeline.press('End');
  await expect(page.getByLabel('Writebacks', { exact: true })).toHaveText('2');
  await expect(page.getByLabel('Writes', { exact: true })).toHaveText('3');
  await timeline.press('Home');
  await timeline.press('ArrowRight');
  await timeline.press('ArrowRight');
  await expect(page.getByTestId('frame-0')).toContainText('Dirty');
  await expect(page.getByLabel('Writebacks', { exact: true })).toHaveText('0');
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByTestId('frame-0')).toContainText('Clean');
  await expect(page.getByLabel('Writebacks', { exact: true })).toHaveText('1');

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Save JSON' }).click(),
  ]);
  const file = await readFile(await download.path());
  expect(JSON.parse(file.toString()).operations).toEqual(['write', 'read', 'read', 'read', 'write', 'write', 'read']);
  await page.getByLabel('Memory references').fill('0');
  await page.getByLabel('Experiment file').setInputFiles({ name: 'mixed.json', mimeType: 'application/json', buffer: file });
  await expect(page.getByLabel('Memory references')).toHaveValue('W:0, 0, 1, 0, W:0, W:0, 2');
  await page.getByRole('button', { name: 'compare view' }).click();
  await page.getByLabel('From frames').fill('1');
  await page.getByLabel('To frames').fill('1');
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  const table = page.getByRole('table', { name: 'Comparison results' });
  await expect(table.getByRole('row')).toHaveCount(5);
  const rows = await table.getByRole('row').all();
  for (const row of rows.slice(1)) {
    await expect(row.getByRole('cell').nth(5)).toHaveText('2');
  }
});
