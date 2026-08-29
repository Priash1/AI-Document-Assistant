import { spawnSync } from 'node:child_process';

const EXPECTED_VERSION = '0.31.1';

if (process.platform === 'win32') {
  throw new Error(
    'Midnight Compact compilation requires WSL2/Linux. The Windows `compact.exe` command is the NTFS compression utility, not the Midnight compiler.',
  );
}

const version = spawnSync('compact', ['compile', '--version'], {
  encoding: 'utf8',
  shell: false,
});
if (version.error || version.status !== 0) {
  throw new Error(
    'Midnight Compact toolchain is unavailable. Install it, then run `compact update 0.31.1` and `compact use 0.31.1`.',
  );
}
const versionText = `${version.stdout}\n${version.stderr}`;
if (!versionText.includes(EXPECTED_VERSION)) {
  throw new Error(
    `PrivateDocs requires Compact ${EXPECTED_VERSION}; compiler reported: ${versionText.trim() || 'unknown version'}`,
  );
}

const compile = spawnSync(
  'compact',
  [
    'compile',
    'contracts/private-docs.compact',
    'contracts/managed/private-docs',
  ],
  { stdio: 'inherit', shell: false },
);
if (compile.error || compile.status !== 0) {
  throw compile.error ?? new Error(`Compact compilation failed with exit code ${compile.status}`);
}
