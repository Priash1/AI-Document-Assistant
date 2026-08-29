# PrivateDocs architecture

## Invariant

The central invariant is:

> No document excerpt is sent to the AI provider unless the exact document digest and canonical query digest have an unconsumed Midnight authorization, and the corresponding nullifier has been finalized and confirmed through the indexer.

The Python layer is intentionally unable to manufacture a successful proof receipt. `MidnightReceipt.from_payload` rejects mock/simulation flags, non-finalized status, unknown networks, malformed contract/transaction identifiers, invalid block heights, and responses that were not independently verified through the indexer.

## Data flow

```text
PDF bytes
  â”œâ”€ domain-separated SHA-256 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â””â”€ PyMuPDF pages â†’ page chunks             â”‚
                                              â–¼
Question â†’ NFC + edge trim â†’ SHA-256 â”€â”€> loopback bridge
                                              â”‚
                                  private circuit arguments
                                              â–¼
                          Compact proof â†’ Midnight transaction
                                              â”‚
                                  indexed ledger membership
                                              â–¼
page chunks â†’ local embeddings â†’ FAISS â†’ selected excerpts
                                              â”‚
                                  finalized consumption first
                                              â–¼
                         OpenAI Responses API (`store=False`)
```

## Digest and commitment domains

The application never treats a plain SHA-256 value as a commitment opening or encryption key.

| Value | Construction | Visibility |
|---|---|---|
| Document digest | `SHA256("privatedocs:document-digest:v1\0" || exact PDF bytes)` | Python + local bridge/proof witness |
| Query digest | `SHA256("privatedocs:query-digest:v1\0" || NFC(edge-trim(question)))` | Python + local bridge/proof witness |
| Owner secret | `SHA256("privatedocs:owner-secret:v1\0" || wallet seed)` | TypeScript bridge/proof witness |
| Document opening | HMAC-SHA256(owner secret, domain + document digest) | TypeScript bridge/proof witness |
| Document commitment | Compact `persistentCommit(documentDigest, documentOpening)` | Ledger |
| Authorization opening | cryptographically random 32 bytes for every authorization | bridge private state + proof witness |
| Authorization commitment | Compact `persistentCommit([documentDigest, queryDigest], authorizationOpening)` | Ledger |
| Nullifier | Compact `persistentHash([domain, authorizationCommitment])` | Ledger |

The stable, keyed document opening makes one PDF map to one revocable commitment per wallet. A fresh authorization opening allows the same exact question to be granted again after a previous authorization is consumed while producing a distinct commitment and nullifier.

## State machine

```text
uploaded
   â”‚ registerDocument finalized + indexed
   â–¼
registered
   â”‚ authorizeQuery(exact query) finalized + indexed
   â–¼
authorized â”€â”€ revokeDocument â”€â”€> revoked
   â”‚ local retrieval + user payload review
   â”‚ consumeQuery finalized + indexed
   â–¼
consumed â”€â”€ authorizeQuery(new opening) â”€â”€> authorized
```

Revocation is permanent for the stable document commitment in a contract deployment. The ledger retains the original registration and authorization records as an audit trail; revocation and consumed-nullifier sets determine whether an operation remains live.

## Ordering and failure behavior

1. Upload validation and PDF extraction happen in memory.
2. Registration and authorization must both yield valid finalized receipts.
3. Only then are document embeddings built and the exact query embedded locally.
4. The user can inspect selected excerpts before consent is consumed.
5. The app checks for an API key before consuming the authorization.
6. Consumption is proved, submitted, finalized, and confirmed through indexed nullifier membership.
7. Only after step 6 does the Responses API call begin.

If steps 1â€“5 fail, the authorization is not consumed. If the provider fails after step 6, the permission remains consumed by design and the user must authorize a new opening. This prevents â€œretryâ€ from becoming an implicit replay.

## Components

- `app.py`: presentation, user-controlled transitions, provider boundary.
- `utils/privacy.py`: digest creation, loopback HTTP client, receipt validation, local UI state mirror.
- `utils/pdf_loader.py`: bounded, in-memory PyMuPDF parsing.
- `utils/chunker.py`: dependency-free page-aware chunks.
- `utils/embeddings.py`: lazy local SentenceTransformer embeddings.
- `utils/vector_store.py`: normalized inner-product FAISS search.
- `utils/chatbot.py`: bounded context serialization, prompt-injection boundary, Responses API call and citation validation.
- `midnight/contracts/private-docs.compact`: owner-authenticated commitment/nullifier state transitions.
- `midnight/src/commitments.ts`: JS-side constructions matching Compact built-ins.
- `midnight/src/bridge.ts`: long-lived wallet/provider process and finalized ledger verification.
- `midnight/scripts/e2e-check.ts`: real proof lifecycle with negative replay/query/revocation checks.

## Verification layers

| Layer | What it establishes | What it does not establish |
|---|---|---|
| Python unit tests | PDF safety, provenance, vector mapping, provider payload, receipt fail-closed behavior | Midnight compilation or proving |
| TypeScript unit tests | 32-byte conversion, domain binding, commitment/nullifier behavior | Ledger acceptance |
| Compact compiler | Contract syntax, type rules and generated circuits | Network deployment |
| Local-devnet E2E | Real proof generation, finalized transactions, indexed state and negative transitions | Public testnet availability |
| Preview/Preprod deployment | Public network address and receipts | Production security review |
