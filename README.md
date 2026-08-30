# PrivateDocs AI

**Zero-knowledge proof-of-permission for private document Q&A.**

PrivateDocs AI turns the original AI Document Assistant into a privacy-gated RAG application for the **Integrate Midnight Hackathon (August 2026)**. A user can upload a PDF, authorize one exact document–question pair through a real Midnight Compact circuit, inspect the minimum context selected locally, consume the one-time authorization on-ledger, and only then call the OpenAI Responses API.

> The application fails closed. If the Midnight bridge, proof server, wallet, node, indexer, deployment, transaction finality, or indexed ledger verification is unavailable, no AI request is made. There is no simulated authorization path.

## Why this is different

A conventional RAG app treats “the user clicked Ask” as permission to send data to an AI provider. PrivateDocs makes that permission explicit and verifiable:

1. The PDF is validated, parsed, chunked, and held in application memory.
2. Domain-separated SHA-256 digests bind the exact PDF bytes and canonical question.
3. A Compact circuit verifies an owner secret and records only commitments on Midnight.
4. Local retrieval runs only after finalized authorization.
5. The user reviews the exact excerpts selected for the provider.
6. Midnight records a deterministic nullifier for that authorization.
7. The OpenAI request starts only after the consumption transaction is finalized and confirmed through the indexer.

The defensible claim is narrow: **Midnight verifies and records a one-time authorization bound to private document/query digests, and the app waits for finalized consumption before invoking the LLM.** It does not prove model correctness, prevent a compromised local runtime from bypassing application code, or imply zero provider retention.

## Privacy boundary

| Location | Receives | Does not receive |
|---|---|---|
| Streamlit process | PDF bytes, extracted pages, local chunks, embeddings, question | — |
| Local Midnight bridge | Domain-separated 32-byte document/query digests | PDF bytes, text, excerpts |
| Proof server | Private circuit inputs/openings required to generate the proof | PDF bytes, text, excerpts |
| Midnight ledger | Document/auth commitments, authorization records, nullifiers, revocation records | PDF bytes, document digest, query digest, openings, owner secret |
| OpenAI Responses API | Exact question and up to five locally selected excerpts | Full PDF, embeddings, Midnight secret/openings |

The API request sets `store=False`. OpenAI documents that ordinary API abuse-monitoring logs may still retain customer content for up to 30 days unless an organization is approved for Modified Abuse Monitoring or Zero Data Retention; `store=False` is therefore not presented as “zero retention.” See [OpenAI API data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint).

## Architecture

```text
Browser
  │ PDF
  ▼
Streamlit / Python ── in-memory PDF parsing, page-aware chunks, FAISS retrieval
  │ documentDigest + queryDigest only
  ▼
127.0.0.1:8787 TypeScript bridge ── wallet, private openings, serialized calls
  │ real proof / transaction
  ▼
Midnight proof server → node → indexer
  │ finalized + indexed consume receipt
  ▼
OpenAI Responses API ── exact question + selected excerpts, store=False
```

Detailed design and threat model: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SECURITY.md](docs/SECURITY.md).

## Midnight protocol

The Compact 0.23 contract exposes four circuits:

| Circuit | Private inputs | Public result |
|---|---|---|
| `registerDocument` | owner secret, document digest, document opening | document commitment in `registeredDocuments` |
| `authorizeQuery` | owner secret, document/query digests, document/auth openings | exact-pair commitment in `authorizedQueries` |
| `consumeQuery` | same exact private values/openings | deterministic nullifier in `consumedNullifiers` |
| `revokeDocument` | owner secret, document digest/opening | document commitment in `revokedDocuments` |

Circuit parameters are private by default in Compact. Commitment outputs can be inserted without disclosing their preimages, following Midnight’s official persistent-commitment pattern. The implementation does not use `ownPublicKey()` for authorization; the [Midnight smart-contract security guide](https://docs.midnight.network/compact/smart-contract-security) warns that it is not cryptographically bound to the transaction signer.

Supported ledger-8 versions are pinned to the current compatibility line:

- Compact toolchain `0.31.1` / language `0.23`
- Midnight.js `4.1.1`
- Wallet SDK `1.2.0`
- Compact runtime `0.16.0`
- Proof server `8.1.0`

Compact `0.34.x` targets the future ledger-9 line and is intentionally not used for current public networks. See the [official support matrix](https://docs.midnight.network/relnotes/support-matrix) and [Compact releases](https://github.com/midnightntwrk/compact/releases).

## Quick start

### 1. Python application

Requirements: Python 3.11–3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key"
streamlit run app.py
```

The OpenAI key is optional until the final consume-and-answer action. Do not commit it; copy `.env.example` only as a variable reference. The default model is [`gpt-5.6-luna`](https://developers.openai.com/api/docs/models/gpt-5.6-luna), configurable with `PRIVATEDOCS_OPENAI_MODEL`.

### 2. Real local Midnight stack

Requirements: Node 22+, Docker Compose v2, and Compact `0.31.1`. On Windows, Midnight’s supported setup requires **WSL2**; the native `compact.exe` is Microsoft’s NTFS compression utility. Follow the [official Windows Compact setup](https://docs.midnight.network/guides/windows-compact-setup).

Inside WSL/Linux:

```bash
cd midnight
npm ci
npm run setup
```

`setup` starts the pinned local node, indexer and proof server, compiles `private-docs.compact`, deploys it with the pre-funded local genesis wallet, and records the deployment in a gitignored state file.

### 3. Bridge

Keep the Midnight stack running, then start:

```bash
cd midnight
npm run bridge
```

The bridge binds only to `127.0.0.1:8787`, rejects unexpected fields, accepts only lowercase 32-byte hex digests, serializes wallet transitions, and returns success only after querying the indexed ledger state. Start Streamlit in another terminal.

## Verification

Python unit tests:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
```

Midnight TypeScript and commitment tests:

```bash
cd midnight
npm run build
npm test
```

Full real proof lifecycle (after `npm run setup`):

```bash
npm run test:e2e
```

The E2E check submits real register, authorize, consume, reauthorize, and revoke transactions. It also confirms that a wrong query, a replayed consumption, and post-revocation consumption are rejected. It does not use a simulator or mock proof receipt.

GitHub Actions contains separate Python, Compact/source, and real local-devnet proof jobs. No CI result should be claimed until the branch is committed and the workflow has actually passed.

## Demo

Use the synthetic agreement at `output/pdf/private-docs-demo-agreement.pdf` and follow [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). The script is timed for the hackathon’s two-minute video requirement and explicitly demonstrates:

- blocked access before proof;
- exact document/query binding;
- public commitment receipt without document/query disclosure;
- provider payload inspection;
- consume-before-AI ordering;
- replay rejection; and
- document revocation.

## What changed from the original project

The protected `pre-midnight-hackathon` tag points to the original single-commit assistant. This branch preserves its PDF extraction, chunking, embedding, FAISS search, and Streamlit workflow while adding:

- in-memory-only upload handling with limits and safe PDF errors;
- page-aware provenance and grounded answer citations;
- lazy local embedding and exact cosine retrieval;
- OpenAI Responses API integration with bounded context and prompt-injection defenses;
- a fail-closed Python Midnight receipt verifier and permission state machine;
- the Compact permission contract, wallet/deployment scaffold, loopback bridge and real E2E test;
- unit tests, CI, threat model, research ledger, demo asset and submission documentation.

## Project layout

```text
app.py                       Streamlit UI and proof-gated workflow
utils/                       PDF, chunking, embedding, FAISS, LLM and privacy modules
tests/                       In-memory Python tests
midnight/contracts/          Compact permission contract
midnight/src/bridge.ts       Real loopback Midnight bridge
midnight/scripts/            Compile guard, cleanup and real E2E lifecycle
docs/                        Architecture, security, research and demo guidance
output/pdf/                  Synthetic, non-sensitive demonstration PDF
scripts/create_demo_pdf.py   Reproducible demo-PDF generator
.github/workflows/ci.yml     Python + Compact + real local-devnet verification
```

## Current verification status

✅ **Real Midnight proof lifecycle verified.**

The `hackathon/private-docs-ai` branch has passed the complete GitHub Actions verification pipeline on Ubuntu:

- **Python privacy + RAG tests:** passed
- **Ruff linting:** passed
- **Compact contract compilation:** passed
- **TypeScript strict build:** passed
- **Midnight commitment/runtime tests:** passed
- **Real local Midnight proof lifecycle:** passed

The real E2E workflow successfully verifies:

1. document registration;
2. exact document–query authorization;
3. rejection of a wrong query;
4. one-time authorization consumption;
5. replay rejection;
6. reauthorization;
7. document revocation; and
8. rejection after revocation.

No simulated authorization path or mocked proof receipt is used.

The verified milestone is preserved by the tag:

`midnight-e2e-verified`

Public Preview/Preprod deployment is not claimed; the verified environment is the real local Midnight devnet used by the automated E2E workflow.