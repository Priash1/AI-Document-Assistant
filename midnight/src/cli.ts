/** Interactive diagnostic client for the loopback PrivateDocs bridge. */
import { stdin, stdout } from 'node:process';
import { createInterface } from 'node:readline/promises';

import { getDeployment, resolveNetwork } from './network';

const HEX_32 = /^[0-9a-f]{64}$/;

function bridgeUrl(): URL {
  const configured = process.env.PRIVATEDOCS_MIDNIGHT_BRIDGE_URL ?? 'http://127.0.0.1:8787';
  const result = new URL(configured);
  if (
    !['http:', 'https:'].includes(result.protocol) ||
    !['127.0.0.1', 'localhost', '::1'].includes(result.hostname) ||
    result.username ||
    result.password ||
    result.search ||
    result.hash
  ) {
    throw new Error('CLI bridge URL must be a credential-free loopback HTTP(S) URL');
  }
  return result;
}

async function callBridge(
  route: string,
  documentDigest: string,
  queryDigest?: string,
): Promise<Record<string, unknown>> {
  const base = bridgeUrl();
  const response = await fetch(new URL(route, `${base.toString().replace(/\/$/, '')}/`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      documentDigest,
      ...(queryDigest ? { queryDigest } : {}),
    }),
    signal: AbortSignal.timeout(5 * 60_000),
  });
  const payload: unknown = await response.json();
  if (!response.ok || !payload || typeof payload !== 'object') {
    throw new Error(`Bridge rejected ${route} with HTTP ${response.status}`);
  }
  return payload as Record<string, unknown>;
}

async function readDigest(
  question: (prompt: string) => Promise<string>,
  label: string,
): Promise<string> {
  const value = (await question(`  ${label} (64 lowercase hex): `)).trim();
  if (!HEX_32.test(value)) throw new Error(`${label} must be 32 lowercase hexadecimal bytes`);
  return value;
}

async function main(): Promise<void> {
  const { network } = resolveNetwork();
  const deployment = getDeployment(network);
  console.log('\nPrivateDocs Midnight permission CLI');
  console.log(`Network:  ${network}`);
  console.log(`Contract: ${deployment?.address ?? 'not deployed'}`);
  console.log(`Bridge:   ${bridgeUrl()}\n`);
  if (!deployment) {
    throw new Error(`No deployment found. Run npm run setup -- --network ${network}`);
  }

  const rl = createInterface({ input: stdin, output: stdout });
  try {
    let running = true;
    while (running) {
      console.log('\n1. Register document');
      console.log('2. Authorize exact query');
      console.log('3. Consume authorization');
      console.log('4. Revoke document');
      console.log('5. Exit\n');
      const choice = (await rl.question('Choice: ')).trim();
      if (choice === '5') {
        running = false;
        continue;
      }
      const routes: Record<string, string> = {
        '1': 'register',
        '2': 'authorize',
        '3': 'consume',
        '4': 'revoke',
      };
      const route = routes[choice];
      if (!route) {
        console.log('Invalid choice.');
        continue;
      }
      try {
        const document = await readDigest(rl.question.bind(rl), 'Document digest');
        const query =
          route === 'authorize' || route === 'consume'
            ? await readDigest(rl.question.bind(rl), 'Query digest')
            : undefined;
        const result = await callBridge(route, document, query);
        console.log(`\nFinalized ${route}:`);
        console.log(`  tx:    ${String(result.txId)}`);
        console.log(`  block: ${String(result.blockHeight)}`);
      } catch (error) {
        console.error(`Operation blocked: ${error instanceof Error ? error.message : 'unknown error'}`);
      }
    }
  } finally {
    rl.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
