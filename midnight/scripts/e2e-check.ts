/**
 * Real end-to-end proof-of-permission check.
 *
 * Requires `npm run setup` first. It starts the loopback bridge, generates
 * synthetic digests, submits real Midnight transactions, verifies finalized
 * receipts, and confirms both wrong-query and replay attempts are rejected.
 */
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { spawn, type ChildProcess } from 'node:child_process';

const BASE_URL = 'http://127.0.0.1:8787';

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitForBridge(child: ChildProcess): Promise<Record<string, unknown>> {
  const deadline = Date.now() + 10 * 60_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`Bridge exited during initialization with code ${child.exitCode}`);
    }
    try {
      const response = await fetch(`${BASE_URL}/health`, {
        signal: AbortSignal.timeout(3_000),
      });
      if (response.ok) {
        const payload = (await response.json()) as Record<string, unknown>;
        if (payload.ok === true && payload.midnightReady === true) return payload;
      }
    } catch {
      // Wallet sync and indexer startup are expected to take time.
    }
    await delay(2_000);
  }
  throw new Error('Bridge did not become ready within ten minutes');
}

async function operation(
  route: string,
  documentDigest: string,
  queryDigest?: string,
): Promise<Response> {
  return fetch(`${BASE_URL}/${route}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      documentDigest,
      ...(queryDigest ? { queryDigest } : {}),
    }),
    signal: AbortSignal.timeout(5 * 60_000),
  });
}

async function finalized(
  route: string,
  documentDigest: string,
  queryDigest?: string,
): Promise<Record<string, unknown>> {
  const response = await operation(route, documentDigest, queryDigest);
  const payload = (await response.json()) as Record<string, unknown>;
  assert.equal(response.status, 200, `${route} failed: ${JSON.stringify(payload)}`);
  assert.equal(payload.ok, true);
  assert.equal(payload.simulated, false);
  assert.equal(payload.status, 'finalized');
  assert.equal(payload.ledgerVerified, true);
  assert.match(String(payload.contractAddress), /^[0-9a-f]{64,}$/);
  assert.match(String(payload.txId), /^[0-9a-f]{64,}$/);
  assert.ok(Number.isSafeInteger(payload.blockHeight) && Number(payload.blockHeight) > 0);
  assert.match(String(payload.documentCommitment), /^[0-9a-f]{64}$/);
  return payload;
}

async function rejected(
  route: string,
  documentDigest: string,
  queryDigest?: string,
): Promise<void> {
  const response = await operation(route, documentDigest, queryDigest);
  assert.notEqual(response.status, 200, `${route} unexpectedly succeeded`);
  const payload = (await response.json()) as Record<string, unknown>;
  assert.equal(payload.ok, false);
}

async function main(): Promise<void> {
  const npmExecutable = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const bridge = spawn(npmExecutable, ['run', 'bridge'], {
    cwd: process.cwd(),
    stdio: ['ignore', 'inherit', 'inherit'],
    shell: false,
  });

  try {
    const health = await waitForBridge(bridge);
    const document = randomBytes(32).toString('hex');
    const allowedQuery = randomBytes(32).toString('hex');
    const wrongQuery = randomBytes(32).toString('hex');

    await finalized('register', document);
    const firstAuthorization = await finalized('authorize', document, allowedQuery);
    assert.match(String(firstAuthorization.authorizationCommitment), /^[0-9a-f]{64}$/);

    await rejected('consume', document, wrongQuery);
    const consumption = await finalized('consume', document, allowedQuery);
    assert.match(String(consumption.nullifier), /^[0-9a-f]{64}$/);
    await rejected('consume', document, allowedQuery);

    const secondAuthorization = await finalized('authorize', document, allowedQuery);
    assert.notEqual(
      secondAuthorization.authorizationCommitment,
      firstAuthorization.authorizationCommitment,
      'fresh authorization must use a distinct opening',
    );
    await finalized('revoke', document);
    await rejected('consume', document, allowedQuery);

    console.log('PrivateDocs real Midnight E2E passed');
    console.log(`  network:  ${String(health.network)}`);
    console.log(`  contract: ${String(health.contractAddress)}`);
    console.log('  checks: register, exact authorization, wrong-query block, consume, replay block, reauthorize, revoke');
  } finally {
    bridge.kill('SIGTERM');
    await Promise.race([
      new Promise<void>((resolve) => bridge.once('exit', () => resolve())),
      delay(10_000),
    ]);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : error);
  process.exit(1);
});
