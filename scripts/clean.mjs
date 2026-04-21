import { rm } from 'node:fs/promises';
import path from 'node:path';

const targets = process.argv.slice(2);

if (targets.length === 0) {
  console.error('Usage: node scripts/clean.mjs <path> [...paths]');
  process.exit(1);
}

await Promise.all(
  targets.map(async (target) => {
    const absolutePath = path.resolve(process.cwd(), target);
    await rm(absolutePath, { force: true, recursive: true });
  })
);
