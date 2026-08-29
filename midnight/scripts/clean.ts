import * as fs from 'node:fs';
import * as path from 'node:path';

const projectRoot = path.resolve(import.meta.dirname, '..');
const targets = [
  'contracts/managed',
  '.midnight-state.json',
  '.midnight-wallet-state',
  '.private-docs-state.json',
  'private-docs-contract-state',
];

for (const relative of targets) {
  const target = path.resolve(projectRoot, relative);
  const relativeCheck = path.relative(projectRoot, target);
  if (relativeCheck.startsWith('..') || path.isAbsolute(relativeCheck)) {
    throw new Error(`Refusing to clean outside the Midnight project: ${target}`);
  }
  fs.rmSync(target, { recursive: true, force: true });
}

process.stdout.write('Removed generated Midnight artifacts and local private state.\n');
