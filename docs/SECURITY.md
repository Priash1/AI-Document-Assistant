# Security and privacy review

## Protected assets

- uploaded PDF bytes and extracted text;
- the userâ€™s exact question;
- selected document excerpts;
- wallet seed, owner secret and commitment openings;
- API credentials;
- integrity of the authorization, consumption and revocation sequence.

## Trust model

This is a hackathon prototype, not a production security boundary. It trusts the local operating-system account, the Python and TypeScript processes, installed dependencies, the configured OpenAI project, and the selected Midnight network components. A malicious process running as the same OS user can inspect process memory or invoke a loopback service; Midnight does not repair a compromised endpoint.

The bridge binds to IPv4 loopback, rejects non-loopback `Host` headers, rejects browser-simple content types, allows no CORS preflight route, accepts only fixed JSON fields, caps request bodies, serializes wallet transitions, and never accepts PDF content. These controls reduce accidental exposure and browser-origin attacks but are not an OS-level sandbox.

## Threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Upload persisted or leaked through a path | Bytes-only upload API; PyMuPDF stream parsing; no upload-save function; upload/vector directories ignored | Streamlit/Python memory and OS paging can contain content |
| Oversized or malicious PDF | 20 MB, 200-page, header, encryption, malformed and empty-text checks; parser errors are sanitized | PyMuPDF remains a trusted native dependency |
| Scanned PDF silently produces bad results | No-text PDFs fail with an OCR-required message | OCR is not implemented |
| Query changed after authorization | Exact canonical query digest; field locks while authorization is active; local state verifies digest equality | NFC + edge trimming is a documented canonicalization choice |
| Fake bridge response unlocks AI | Python rejects simulation/mock flags, non-final status, malformed IDs and missing indexer verification | A compromised local Python process can bypass its own code |
| Proof created but not on ledger | Bridge waits for finalized SDK receipt and independently polls indexed Set membership | Indexer/node trust and chain reorganization assumptions remain |
| Authorization replay | Deterministic nullifier; circuit rejects existing nullifier; local bridge also refuses consumed records | Losing local opening state can strand an authorization |
| Wrong query uses a valid document grant | Authorization commitment binds both private digests; bridge state key binds both | Collision resistance of selected hashes/commitments is assumed |
| Revoked document still consumed | Consume circuit recomputes document commitment and asserts it is absent from revocation set | Revocation cannot recall context already sent before revocation |
| `ownPublicKey()` impersonation | Not used; owner authentication proves knowledge of a private secret committed at construction | Bridge access still delegates use of that secret to local callers |
| Prompt injection in PDF | Excerpts are serialized as untrusted JSON; system instructions forbid following embedded commands; citations must reference supplied pages | Model behavior is probabilistic, not a formal security proof |
| Excessive context disclosure | Local top-5 retrieval, 20,000-character limit, exact payload preview | Retrieved excerpts can still contain sensitive information |
| API key leak | Environment/Streamlit secret only; `.env*` ignored; public errors sanitized | User environment and provider account remain trusted |
| Misleading no-retention claim | UI says request storage is disabled and documents residual provider-retention limits | Default abuse-monitoring retention may be up to 30 days |
| Secret committed to Git | Wallet, private state, proofs, seeds, mnemonics, keys and `.env` patterns ignored; pre-submit secret scan | Ignore rules do not protect secrets intentionally force-added |

## Proof-server privacy

The proof server receives private witness material needed to generate the zero-knowledge proof. Running it locally keeps that material on the user-controlled machine, but â€œzero knowledge on the ledgerâ€ does not mean the prover sees no private inputs. A remote proof-server URL is therefore an explicit trust expansion and should not be used for sensitive data without an operator/privacy assessment.

The bridge sends the proof server digests and openingsâ€”not PDF bytes, extracted text, questions, or excerpts. Query text is converted to a digest in Python before crossing the bridge.

## Provider data controls

The app passes `store=False` to `/v1/responses`, which avoids opting into response application-state storage. According to [OpenAIâ€™s API data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint), default abuse-monitoring logs can contain prompts/responses and may be retained for up to 30 days. Zero Data Retention or Modified Abuse Monitoring requires provider approval and project configuration. Judges should not interpret the UIâ€™s â€œstorage disabledâ€ label as a claim of ordinary-account zero retention.

## Before production

- replace direct bridge trust with authenticated IPC and OS access controls;
- use a dedicated secret manager/HSM and audited key rotation;
- encrypt and recover pending authorization-opening state transactionally;
- add dependency/SBOM and native-PDF-parser security scanning;
- add tenancy and per-user authorization rather than one operator secret;
- obtain a third-party Compact/circuit review;
- define chain-finality and indexer-divergence policies;
- add explicit data classification, DPA/BAA/regional-processing controls;
- add OCR sandboxing if scanned documents are supported;
- deploy behind a hardened service boundary rather than Streamlitâ€™s development server.
