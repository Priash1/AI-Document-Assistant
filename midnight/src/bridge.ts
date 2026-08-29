/**
 * Loopback-only HTTP bridge between Streamlit and a real Midnight deployment.
 *
 * This process never accepts PDF text. It serializes wallet transactions,
 * submits real Compact circuit calls, then independently queries indexed
 * ledger state before returning a finalized receipt to Python.
 */
import * as fs from 'node:fs';
import { createHmac, randomBytes } from 'node:crypto';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import * as path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { findDeployedContract } from '@midnight-ntwrk/midnight-js-contracts';
import { httpClientProofProvider } from '@midnight-ntwrk/midnight-js-http-client-proof-provider';
import { indexerPublicDataProvider } from '@midnight-ntwrk/midnight-js-indexer-public-data-provider';
import { levelPrivateStateProvider } from '@midnight-ntwrk/midnight-js-level-private-state-provider';
import { NodeZkConfigProvider } from '@midnight-ntwrk/midnight-js-node-zk-config-provider';
import { CompiledContract } from '@midnight-ntwrk/midnight-js-protocol/compact-js';
import { WebSocket } from 'ws';

import {
  authorizationCommitment,
  authorizationNullifier,
  bytesToHex,
  deriveDocumentOpening,
  deriveOwnerSecret,
  documentCommitment,
  hexToBytes32,
} from './commitments';
import {
  formatWalletBackupNotice,
  getDeployment,
  getOrCreateWallet,
  resolveNetwork,
  type NetworkId,
} from './network';
import { createWallet, persistWalletState, type WalletContext } from './wallet';

// @ts-expect-error Midnight wallet sync requires a global WebSocket constructor.
globalThis.WebSocket = WebSocket;

const PRIVATE_STATE_ID = 'privateDocsPrivateState';
const PRIVATE_STORE_NAME = 'private-docs-contract-state';
const BRIDGE_STATE_FILE = '.private-docs-state.json';
const MAX_BODY_BYTES = 4 * 1024;
const MAX_STATE_ENTRIES = 10_000;
const DEFAULT_PORT = 8787;
const HEX_32 = /^[0-9a-f]{64}$/;

type Operation = 'register' | 'authorize' | 'consume' | 'revoke';
type AuthorizationStatus = 'pending' | 'active' | 'consumed';

interface AuthorizationRecord {
  opening: string;
  commitment: string;
  status: AuthorizationStatus;
  updatedAt: string;
}

interface BridgePrivateState {
  version: 1;
  authorizations: Record<string, AuthorizationRecord>;
}

interface RuntimeContext {
  network: NetworkId;
  deploymentAddress: string;
  ownerSecret: Uint8Array;
  wallet: WalletContext;
  providers: any;
  deployed: any;
  contractModule: any;
}

interface ReceiptOptions {
  operation: Operation;
  runtime: RuntimeContext;
  tx: any;
  documentCommitment: Uint8Array;
  authorizationCommitment?: Uint8Array;
  nullifier?: Uint8Array;
}

function bridgeStatePath(): string {
  return path.resolve(process.cwd(), BRIDGE_STATE_FILE);
}

function emptyBridgeState(): BridgePrivateState {
  return { version: 1, authorizations: {} };
}

function loadBridgeState(): BridgePrivateState {
  const statePath = bridgeStatePath();
  if (!fs.existsSync(statePath)) return emptyBridgeState();
  let parsed: unknown;
  try {
    parsed = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  } catch {
    throw new Error(`Cannot parse ${BRIDGE_STATE_FILE}; move it aside and re-authorize`);
  }
  if (
    !parsed ||
    typeof parsed !== 'object' ||
    (parsed as { version?: unknown }).version !== 1 ||
    !(parsed as { authorizations?: unknown }).authorizations ||
    typeof (parsed as { authorizations?: unknown }).authorizations !== 'object'
  ) {
    throw new Error(`${BRIDGE_STATE_FILE} has an unsupported schema`);
  }
  const state = parsed as BridgePrivateState;
  if (Object.keys(state.authorizations).length > MAX_STATE_ENTRIES) {
    throw new Error(`${BRIDGE_STATE_FILE} exceeds the safe entry limit`);
  }
  for (const record of Object.values(state.authorizations)) {
    if (
      !record ||
      !HEX_32.test(record.opening) ||
      !HEX_32.test(record.commitment) ||
      !['pending', 'active', 'consumed'].includes(record.status)
    ) {
      throw new Error(`${BRIDGE_STATE_FILE} contains an invalid authorization record`);
    }
  }
  return state;
}

function saveBridgeState(state: BridgePrivateState): void {
  const statePath = bridgeStatePath();
  const temporary = `${statePath}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(temporary, statePath);
}

function authorizationStateKey(
  ownerSecret: Uint8Array,
  documentDigest: Uint8Array,
  queryDigest: Uint8Array,
): string {
  return createHmac('sha256', ownerSecret)
    .update('privatedocs:authorization-state:v1\0', 'utf8')
    .update(documentDigest)
    .update(queryDigest)
    .digest('hex');
}

function privateStatePassword(): string {
  const configured = process.env.PRIVATE_STATE_PASSWORD?.trim();
  if (configured) {
    if (configured.length < 16) {
      throw new Error('PRIVATE_STATE_PASSWORD must contain at least 16 characters');
    }
    return configured;
  }
  if (resolveNetwork().network !== 'undeployed') {
    throw new Error(
      'PRIVATE_STATE_PASSWORD is required for preview and preprod and must contain at least 16 characters',
    );
  }
  return 'Local-Devnet-Development-Placeholder-1';
}

function buildProviders(walletCtx: WalletContext, zkConfigPath: string, networkConfig: any) {
  const walletProvider = {
    getCoinPublicKey: () => walletCtx.shieldedSecretKeys.coinPublicKey,
    getEncryptionPublicKey: () => walletCtx.shieldedSecretKeys.encryptionPublicKey,
    async balanceTx(tx: any, ttl?: Date) {
      const recipe = await walletCtx.wallet.balanceUnboundTransaction(
        tx,
        {
          shieldedSecretKeys: walletCtx.shieldedSecretKeys,
          dustSecretKey: walletCtx.dustSecretKey,
        },
        { ttl: ttl ?? new Date(Date.now() + 30 * 60 * 1000) },
      );
      return walletCtx.wallet.finalizeRecipe(recipe);
    },
    submitTx: (tx: any) => walletCtx.wallet.submitTransaction(tx) as any,
  };
  const zkConfigProvider = new NodeZkConfigProvider(zkConfigPath);
  const accountId = walletCtx.unshieldedKeystore.getBech32Address().toString();
  return {
    privateStateProvider: levelPrivateStateProvider({
      privateStateStoreName: PRIVATE_STORE_NAME,
      accountId,
      privateStoragePasswordProvider: privateStatePassword,
    }),
    publicDataProvider: indexerPublicDataProvider(
      networkConfig.indexer,
      networkConfig.indexerWS,
    ),
    zkConfigProvider,
    proofProvider: httpClientProofProvider(networkConfig.proofServer, zkConfigProvider),
    walletProvider,
    midnightProvider: walletProvider,
  };
}

async function initializeRuntime(): Promise<RuntimeContext> {
  const { network, config } = resolveNetwork();
  const deployment = getDeployment(network);
  if (!deployment) {
    throw new Error(`No PrivateDocs deployment for ${network}; run npm run setup first`);
  }

  const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
  const zkConfigPath = path.resolve(
    currentDirectory,
    '..',
    'contracts',
    'managed',
    'private-docs',
  );
  const contractPath = path.join(zkConfigPath, 'contract', 'index.js');
  if (!fs.existsSync(contractPath)) {
    throw new Error('PrivateDocs contract is not compiled; run npm run compile first');
  }

  const contractModule = await import(pathToFileURL(contractPath).href);
  const compiledContract = CompiledContract.make(
    'private-docs',
    contractModule.Contract,
  ).pipe(
    CompiledContract.withVacantWitnesses,
    CompiledContract.withCompiledFileAssets(zkConfigPath),
  );

  const walletCredentials = getOrCreateWallet(network);
  const notice = formatWalletBackupNotice(walletCredentials, network);
  if (notice) process.stdout.write(`${notice}\n`);
  const ownerSecret = deriveOwnerSecret(walletCredentials.seed);
  const wallet = await createWallet({
    network,
    networkConfig: config,
    seed: walletCredentials.seed,
  });
  await wallet.wallet.waitForSyncedState();
  await persistWalletState(network, wallet);

  const providers = buildProviders(wallet, zkConfigPath, config);
  const deployed = await findDeployedContract(providers, {
    compiledContract: compiledContract as any,
    contractAddress: deployment.address,
    privateStateId: PRIVATE_STATE_ID,
    initialPrivateState: {},
  });
  const indexed = await providers.publicDataProvider.queryContractState(
    deployment.address,
  );
  if (!indexed) {
    await wallet.wallet.stop();
    throw new Error('PrivateDocs deployment is not available through the indexer');
  }

  return {
    network,
    deploymentAddress: deployment.address,
    ownerSecret,
    wallet,
    providers,
    deployed,
    contractModule,
  };
}

async function queryLedger(runtime: RuntimeContext): Promise<any> {
  const state = await runtime.providers.publicDataProvider.queryContractState(
    runtime.deploymentAddress,
  );
  if (!state) throw new Error('Indexer returned no contract state');
  return runtime.contractModule.ledger(state.data);
}

async function waitForLedger(
  runtime: RuntimeContext,
  predicate: (ledger: any) => boolean,
): Promise<void> {
  const deadline = Date.now() + 90_000;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      if (predicate(await queryLedger(runtime))) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(
    `Finalized transaction was not verified through the indexer${
      lastError instanceof Error ? `: ${lastError.message}` : ''
    }`,
  );
}

function transactionId(tx: any): string {
  const value = tx?.public?.txId;
  const normalized = typeof value === 'string' ? value : value?.toString?.();
  if (typeof normalized !== 'string' || !/^[0-9a-fA-F]{64,}$/.test(normalized)) {
    throw new Error('Midnight SDK returned an invalid transaction identifier');
  }
  return normalized.toLowerCase();
}

function transactionBlockHeight(tx: any): number {
  const value = tx?.public?.blockHeight;
  const numeric = typeof value === 'bigint' ? Number(value) : Number(value);
  if (!Number.isSafeInteger(numeric) || numeric <= 0) {
    throw new Error('Midnight SDK returned an invalid finalized block height');
  }
  return numeric;
}

function receipt(options: ReceiptOptions): Record<string, unknown> {
  return {
    ok: true,
    simulated: false,
    status: 'finalized',
    network: options.runtime.network,
    contractAddress: options.runtime.deploymentAddress.toLowerCase(),
    txId: transactionId(options.tx),
    blockHeight: transactionBlockHeight(options.tx),
    ledgerVerified: true,
    documentCommitment: bytesToHex(options.documentCommitment),
    ...(options.authorizationCommitment
      ? { authorizationCommitment: bytesToHex(options.authorizationCommitment) }
      : {}),
    ...(options.nullifier ? { nullifier: bytesToHex(options.nullifier) } : {}),
  };
}

async function performOperation(
  runtime: RuntimeContext,
  operation: Operation,
  documentDigestHex: string,
  queryDigestHex?: string,
): Promise<Record<string, unknown>> {
  const documentDigest = hexToBytes32(documentDigestHex, 'documentDigest');
  const documentOpening = deriveDocumentOpening(runtime.ownerSecret, documentDigest);
  const document = documentCommitment(documentDigest, documentOpening);

  if (operation === 'register') {
    const tx = await runtime.deployed.callTx.registerDocument(
      runtime.ownerSecret,
      documentDigest,
      documentOpening,
    );
    await waitForLedger(runtime, (ledger) =>
      Boolean(ledger.registeredDocuments.member(document)),
    );
    return receipt({ operation, runtime, tx, documentCommitment: document });
  }

  if (operation === 'revoke') {
    const tx = await runtime.deployed.callTx.revokeDocument(
      runtime.ownerSecret,
      documentDigest,
      documentOpening,
    );
    await waitForLedger(runtime, (ledger) =>
      Boolean(ledger.revokedDocuments.member(document)),
    );
    return receipt({ operation, runtime, tx, documentCommitment: document });
  }

  if (!queryDigestHex) throw new Error(`${operation} requires queryDigest`);
  const queryDigest = hexToBytes32(queryDigestHex, 'queryDigest');
  const state = loadBridgeState();
  const key = authorizationStateKey(runtime.ownerSecret, documentDigest, queryDigest);

  if (operation === 'authorize') {
    const existing = state.authorizations[key];
    if (existing?.status === 'active') {
      throw new Error('This document-query pair already has an active authorization');
    }
    const opening = randomBytes(32);
    const authorization = authorizationCommitment(documentDigest, queryDigest, opening);
    state.authorizations[key] = {
      opening: bytesToHex(opening),
      commitment: bytesToHex(authorization),
      status: 'pending',
      updatedAt: new Date().toISOString(),
    };
    saveBridgeState(state);
    try {
      const tx = await runtime.deployed.callTx.authorizeQuery(
        runtime.ownerSecret,
        documentDigest,
        documentOpening,
        queryDigest,
        opening,
      );
      await waitForLedger(runtime, (ledger) =>
        Boolean(ledger.authorizedQueries.member(authorization)),
      );
      state.authorizations[key] = {
        ...state.authorizations[key],
        status: 'active',
        updatedAt: new Date().toISOString(),
      };
      saveBridgeState(state);
      return receipt({
        operation,
        runtime,
        tx,
        documentCommitment: document,
        authorizationCommitment: authorization,
      });
    } catch (error) {
      delete state.authorizations[key];
      saveBridgeState(state);
      throw error;
    }
  }

  const record = state.authorizations[key];
  if (!record || record.status !== 'active') {
    throw new Error('No active local authorization exists for this document-query pair');
  }
  const opening = hexToBytes32(record.opening, 'authorization opening');
  const authorization = authorizationCommitment(documentDigest, queryDigest, opening);
  if (bytesToHex(authorization) !== record.commitment) {
    throw new Error('Private authorization state failed its commitment check');
  }
  const nullifier = authorizationNullifier(authorization);
  const tx = await runtime.deployed.callTx.consumeQuery(
    runtime.ownerSecret,
    documentDigest,
    documentOpening,
    queryDigest,
    opening,
  );
  await waitForLedger(runtime, (ledger) =>
    Boolean(ledger.consumedNullifiers.member(nullifier)),
  );
  state.authorizations[key] = {
    ...record,
    status: 'consumed',
    updatedAt: new Date().toISOString(),
  };
  saveBridgeState(state);
  return receipt({
    operation,
    runtime,
    tx,
    documentCommitment: document,
    authorizationCommitment: authorization,
    nullifier,
  });
}

async function readJsonBody(request: IncomingMessage): Promise<Record<string, unknown>> {
  const contentType = request.headers['content-type']?.split(';', 1)[0]?.trim();
  if (contentType !== 'application/json') {
    throw new Error('Content-Type must be application/json');
  }
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_BODY_BYTES) throw new Error('Request body is too large');
    chunks.push(buffer);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new Error('Request body must be valid JSON');
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Request body must be a JSON object');
  }
  return parsed as Record<string, unknown>;
}

function validateOperationBody(
  operation: Operation,
  body: Record<string, unknown>,
): { documentDigest: string; queryDigest?: string } {
  const expected = new Set(
    operation === 'authorize' || operation === 'consume'
      ? ['documentDigest', 'queryDigest']
      : ['documentDigest'],
  );
  if (Object.keys(body).some((key) => !expected.has(key)) || Object.keys(body).length !== expected.size) {
    throw new Error('Request contains unexpected or missing fields');
  }
  if (typeof body.documentDigest !== 'string' || !HEX_32.test(body.documentDigest)) {
    throw new Error('documentDigest must be 32 lowercase hexadecimal bytes');
  }
  if (expected.has('queryDigest')) {
    if (typeof body.queryDigest !== 'string' || !HEX_32.test(body.queryDigest)) {
      throw new Error('queryDigest must be 32 lowercase hexadecimal bytes');
    }
    return { documentDigest: body.documentDigest, queryDigest: body.queryDigest };
  }
  return { documentDigest: body.documentDigest };
}

function sendJson(response: ServerResponse, status: number, payload: Record<string, unknown>): void {
  const body = Buffer.from(`${JSON.stringify(payload)}\n`, 'utf8');
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': String(body.length),
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
  });
  response.end(body);
}

const runtimePromise = initializeRuntime();
let readyRuntime: RuntimeContext | null = null;
let startupError: Error | null = null;
runtimePromise.then(
  (runtime) => {
    readyRuntime = runtime;
    process.stdout.write(
      `PrivateDocs Midnight bridge ready on ${runtime.network} for ${runtime.deploymentAddress}\n`,
    );
  },
  (error: unknown) => {
    startupError = error instanceof Error ? error : new Error('Unknown startup failure');
    process.stderr.write(`PrivateDocs Midnight initialization failed: ${startupError.message}\n`);
  },
);

let transitionQueue: Promise<unknown> = Promise.resolve();
function serialized<T>(work: () => Promise<T>): Promise<T> {
  const next = transitionQueue.then(work, work);
  transitionQueue = next.catch(() => undefined);
  return next;
}

const routeToOperation: Record<string, Operation> = {
  '/register': 'register',
  '/authorize': 'authorize',
  '/consume': 'consume',
  '/revoke': 'revoke',
};

const server = createServer(async (request, response) => {
  try {
    const allowedHosts = new Set([
      `127.0.0.1:${configuredPort}`,
      `localhost:${configuredPort}`,
    ]);
    if (!request.headers.host || !allowedHosts.has(request.headers.host.toLowerCase())) {
      sendJson(response, 403, { ok: false, error: 'Loopback host required' });
      return;
    }
    const requestUrl = new URL(request.url ?? '/', 'http://127.0.0.1');
    if (requestUrl.search || requestUrl.hash) {
      sendJson(response, 404, { ok: false, error: 'Route not found' });
      return;
    }
    if (request.method === 'GET' && requestUrl.pathname === '/health') {
      if (!readyRuntime) {
        sendJson(response, 503, {
          ok: false,
          midnightReady: false,
          simulated: false,
          error: startupError ? 'Midnight initialization failed' : 'Midnight initialization pending',
        });
        return;
      }
      await queryLedger(readyRuntime);
      sendJson(response, 200, {
        ok: true,
        midnightReady: true,
        simulated: false,
        network: readyRuntime.network,
        contractAddress: readyRuntime.deploymentAddress,
      });
      return;
    }

    const operation = routeToOperation[requestUrl.pathname];
    if (request.method !== 'POST' || !operation) {
      sendJson(response, 404, { ok: false, error: 'Route not found' });
      return;
    }
    if (!readyRuntime) {
      sendJson(response, 503, { ok: false, error: 'Real Midnight stack is not ready' });
      return;
    }
    const body = validateOperationBody(operation, await readJsonBody(request));
    const result = await serialized(() =>
      performOperation(
        readyRuntime as RuntimeContext,
        operation,
        body.documentDigest,
        body.queryDigest,
      ),
    );
    sendJson(response, 200, result);
  } catch (error) {
    // Never echo request values or SDK error payloads back to Python.
    const message = error instanceof Error ? error.message : 'Unknown bridge error';
    const validationFailure =
      message.includes('must be') ||
      message.includes('unexpected or missing') ||
      message.includes('too large');
    const conflict =
      message.includes('already') ||
      message.includes('No active') ||
      message.includes('revoked');
    process.stderr.write(`PrivateDocs bridge operation failed: ${message}\n`);
    sendJson(response, validationFailure ? 400 : conflict ? 409 : 502, {
      ok: false,
      error: validationFailure
        ? 'Invalid bridge request'
        : conflict
          ? 'Midnight permission transition rejected'
          : 'Midnight operation failed safely',
    });
  }
});

const configuredPort = Number(process.env.PRIVATEDOCS_MIDNIGHT_BRIDGE_PORT ?? DEFAULT_PORT);
if (!Number.isSafeInteger(configuredPort) || configuredPort < 1024 || configuredPort > 65_535) {
  throw new Error('PRIVATEDOCS_MIDNIGHT_BRIDGE_PORT must be an integer from 1024 to 65535');
}
server.headersTimeout = 10_000;
server.requestTimeout = 5 * 60_000;
server.listen(configuredPort, '127.0.0.1', () => {
  process.stdout.write(`PrivateDocs bridge listening at http://127.0.0.1:${configuredPort}\n`);
});

async function shutdown(): Promise<void> {
  server.close();
  if (readyRuntime) {
    await persistWalletState(readyRuntime.network, readyRuntime.wallet);
    await readyRuntime.wallet.wallet.stop();
  }
}

process.once('SIGINT', () => void shutdown().finally(() => process.exit(0)));
process.once('SIGTERM', () => void shutdown().finally(() => process.exit(0)));
