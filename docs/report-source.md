# PrivateDocs Midnight implementation research

**Research date:** 2026-08-29
**Scope:** Hackathon rules, supported Midnight ledger-8 stack, Compact privacy/security patterns, Windows constraints, Midnight.js integration, and OpenAI provider-boundary claims.
**Decision summary:** Build an exact document/query commitment, one-time nullifier and revocation protocol using Compact 0.23 / toolchain 0.31.1 and Midnight.js 4.1.1. Use a long-lived loopback TypeScript bridge because no official Python Midnight SDK is available in the supported stack. Consume and verify indexed ledger state before the LLM call. Never present a JavaScript simulator or locally fabricated receipt as Midnight proof evidence.

## Findings

1. The current public Midnight networks use the ledger-8 compatibility line; the newer Compact 0.34 line targets ledger 9 and is not the correct current-mainnet target.
2. Compact circuit inputs are private unless explicitly disclosed. `persistentCommit` can place a commitment on the ledger without revealing its value/opening.
3. `ownPublicKey()` is caller-supplied and is not safe authentication. A private secret committed at contract construction is used instead.
4. A proof server processes private witness inputs. Local proving reduces disclosure to external operators, but it must remain inside the documented trust boundary.
5. Midnightâ€™s supported Windows workflow requires WSL. Native Windows `compact.exe` is unrelated NTFS compression tooling.
6. The official scaffold provides wallet, node, indexer, proof-server and deployment plumbing. It was pinned and adapted instead of recreating that stack.
7. A Responses API call with `store=False` should be described as application-state storage disabled, not zero retention; ordinary abuse-monitoring retention can still apply.

## Source ledger

| Source | Published/updated | Accessed | Relevance |
|---|---|---|---|
| [Integrate Midnight Hackathon](https://midnight-hackathon-august-2026.devpost.com/) | August 2026 event page | 2026-08-29 | Deadline, submission requirements, judging criteria and two-minute demo constraint |
| [Midnight support matrix](https://docs.midnight.network/relnotes/support-matrix) | current documentation | 2026-08-29 | Compatible ledger, Compact, Midnight.js, wallet and proof-server versions |
| [Compact releases](https://github.com/midnightntwrk/compact/releases) | 0.31.1 and 0.34.0 release notes, August 2026 | 2026-08-29 | Confirms 0.31.1/language 0.23 for current ledger 8 and 0.34â€™s future ledger-9 target |
| [Create Midnight App](https://github.com/midnightntwrk/create-mn-app) | v0.5.0 current scaffold | 2026-08-29 | Official local devnet, compile, wallet, deploy and network scaffold |
| [Windows Compact setup](https://docs.midnight.network/guides/windows-compact-setup) | current documentation | 2026-08-29 | WSL requirement and supported Windows workflow |
| [Installation guide](https://docs.midnight.network/getting-started/installation) | current documentation | 2026-08-29 | Node, Docker and Compact prerequisites |
| [Smart contract security](https://docs.midnight.network/compact/smart-contract-security) | current documentation | 2026-08-29 | Security guidance, especially unsafe `ownPublicKey()` authentication |
| [Private guest-list contract](https://docs.midnight.network/examples/contracts/private-guest-list) | current documentation | 2026-08-29 | Official Set, private secret, `persistentCommit`, `persistentHash`, membership and owner-auth patterns |
| [Compact JavaScript runtime](https://docs.midnight.network/guides/compact-javascript-runtime) | current documentation | 2026-08-29 | Runtime commitment/hash behavior and generated contract integration |
| [Deploy and operate](https://docs.midnight.network/guides/deploy-and-operate) | current documentation | 2026-08-29 | Node/indexer/proof-server deployment responsibilities |
| [OpenAI models](https://developers.openai.com/api/docs/models) | current 2026 catalog | 2026-08-29 | Responses-capable `gpt-5.6-luna` default and intended cost-sensitive use |
| [OpenAI API data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) | current documentation | 2026-08-29 | `store` behavior, application-state storage, abuse-monitoring retention and ZDR limitations |

## Claim ledger

| Claim | Status | Evidence/limit |
|---|---|---|
| â€œPDF/question are not stored on Midnightâ€ | Supported by source and code | Contract accepts private digests/openings and stores only commitments/nullifiers; raw PDF never crosses the bridge |
| â€œOne exact query authorization is single-useâ€ | Source-level implemented; needs real E2E evidence | Authorization binds both digests; deterministic nullifier Set blocks replay |
| â€œRevocation blocks outstanding document authorizationsâ€ | Source-level implemented; needs real E2E evidence | Consume asserts the recomputed document commitment is not revoked |
| â€œThe app uses real Midnightâ€ | Only after compile/deploy/E2E passes | Source uses real SDK/proof server/node/indexer and refuses simulation; no deployment is claimed yet |
| â€œOpenAI stores nothingâ€ | Rejected | `store=False` does not eliminate default abuse-monitoring retention; UI/docs use narrower wording |
| â€œMidnight prevents a modified Python app from bypassing the gateâ€ | Rejected | The contract proves transitions; enforcement ordering is application code and local-runtime trust |
