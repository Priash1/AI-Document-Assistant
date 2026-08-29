# PrivateDocs Midnight protocol

This directory is the real Midnight half of PrivateDocs AI. It was generated from `create-mn-app` 0.5.0’s official hello-world scaffold, then adapted to a Compact proof-of-permission contract and a loopback TypeScript bridge.

It contains no simulated proof service and no success fallback. A bridge operation succeeds only when the Midnight SDK returns a finalized transaction and the public data provider confirms the expected commitment/nullifier membership in indexed ledger state.

## Supported stack

- Node.js 22+
- Docker with Compose v2
- Compact toolchain 0.31.1 (language 0.23)
- Midnight.js 4.1.1
- Wallet SDK 1.2.0
- Compact runtime 0.16.0
- Proof server 8.1.0
- Ledger-8 local node/indexer images pinned in `docker-compose.yml`

Do not update this project to Compact 0.34 merely because it is newer: that line targets ledger 9, while the current public networks use ledger 8.

## Local devnet

On Linux/WSL:

```bash
npm ci
npm run setup
```

`setup` performs, in order:

1. `docker compose up -d --wait` for the local node, indexer and proof server;
2. version-checked compilation of `contracts/private-docs.compact`;
3. wallet synchronization, NIGHT-to-DUST registration and a real deployment;
4. persistence of the deployment address in `.midnight-state.json`.

The local devnet uses the public, pre-funded genesis seed from the official scaffold. Never use that seed for a public network or real value.

## Windows warning

Use WSL2. Native Windows resolves `compact` to `C:\Windows\System32\compact.exe`, an NTFS compression utility. `npm run compile` detects Windows and refuses to invoke it. Follow Midnight’s official Windows/WSL setup guide before attempting real circuit compilation or proving.

## Start the bridge

After setup:

```bash
npm run bridge
```

The server listens only on `127.0.0.1:8787` and exposes:

| Method/path | Circuit/action |
|---|---|
| `GET /health` | Confirms wallet, deployment and indexed contract state are ready |
| `POST /register` | `registerDocument` |
| `POST /authorize` | `authorizeQuery` |
| `POST /consume` | `consumeQuery` |
| `POST /revoke` | `revokeDocument` |

POST bodies accept only `documentDigest` and, where required, `queryDigest`; each must be exactly 64 lowercase hex characters. The bridge never accepts document bytes, extracted text, questions or excerpts.

## Contract state

`private-docs.compact` stores four public Sets of 32-byte values:

- `registeredDocuments`: stable document commitments;
- `authorizedQueries`: fresh commitments binding one private document/query pair;
- `consumedNullifiers`: deterministic authorization nullifiers;
- `revokedDocuments`: permanently revoked document commitments.

The sealed owner commitment is initialized from a private owner secret derived from the wallet seed. Every state-changing circuit proves knowledge of that secret. `ownPublicKey()` is intentionally not used.

The bridge derives stable document openings from an owner-keyed HMAC and keeps fresh authorization openings in `.private-docs-state.json`. The state key is also owner-keyed, so the file does not store raw document/query digests. This file, wallet state, generated proof assets, seeds and contract private-state databases are gitignored.

## Tests

Source/type and cryptographic helper tests (no proof claim):

```bash
npm run build
npm test
```

Real lifecycle test after `npm run setup`:

```bash
npm run test:e2e
```

The E2E process starts the actual bridge and submits real transactions for register, authorize, consume, reauthorize and revoke. It asserts that wrong-query consumption, replay and post-revocation consumption fail.

## Public Preview/Preprod

The scaffold supports `--network preview` and `--network preprod`:

```bash
npm run setup -- --network preview
```

The command creates or restores a wallet, prints its address and faucet URL, waits for funding, and deploys to the selected network. For non-local networks:

- set a strong `PRIVATE_STATE_PASSWORD` of at least 16 characters;
- protect `MIDNIGHT_WALLET_MNEMONIC` / `MIDNIGHT_WALLET_SEED` and never place them on a command line or in Git;
- prefer a local proof server because it receives private witness values;
- do not claim a public deployment until the address and real receipts have been independently checked.

## Scripts

| Command | Purpose |
|---|---|
| `npm run compile` | Refuse Windows collision, enforce Compact 0.31.1, compile the contract |
| `npm run build` | Strict TypeScript type-check; failures are not masked |
| `npm test` | Commitment and nullifier unit tests |
| `npm run setup` | Start required services, compile and deploy |
| `npm run bridge` | Start the serialized real Midnight bridge |
| `npm run cli` | Interactively call the running bridge with digests |
| `npm run test:e2e` | Full real permission lifecycle and negative cases |
| `npm run network <name>` | Select `undeployed`, `preview` or `preprod` |
| `npm run check-balance` | Inspect wallet NIGHT/DUST balance |
| `npm run clean` | Delete generated contract artifacts and local private/wallet/deployment state |

`npm run clean` is destructive to local Midnight state and testnet wallet/deployment records. Back up any recovery phrase before using it.
