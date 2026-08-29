# Two-minute demo script

Use only the synthetic agreement in `output/pdf/private-docs-demo-agreement.pdf`. The demo should display the hackathon name and the repository URL in the first frame.

## Before recording

- Start the local Midnight stack with `npm run setup` inside WSL/Linux.
- Start the bridge with `npm run bridge`.
- Set `OPENAI_API_KEY` in the Streamlit terminal; never show the key.
- Start `streamlit run app.py`.
- Confirm `npm run test:e2e` has passed and keep one receipt available as backup evidence.
- Use the exact question: **“What obligations survive termination?”**

## Narration and timing

**0:00–0:12 — Problem**

“This is PrivateDocs AI for the Integrate Midnight Hackathon. Normal document assistants treat a click as permission to disclose context. PrivateDocs requires a verifiable, one-time permission for one exact document and question.”

**0:12–0:28 — Private upload**

Upload the synthetic agreement. Point to pages/chunks and the in-memory notice.

“The PDF is validated and parsed in memory. The chain and bridge receive only a domain-separated digest—not the file or its text.”

**0:28–0:42 — Fail closed**

Enter the question but pause before authorizing. Show “AI boundary is closed.”

“Before proof, retrieval and the AI request are blocked.”

**0:42–1:02 — Real authorization**

Click **Generate and finalize Midnight authorization**. Show the finalized receipt.

“The Compact circuit privately checks the owner secret and binds this document digest to this exact query digest. The ledger gets commitments only. The app waits for finality and verifies indexed state—there is no simulator fallback.”

**1:02–1:20 — Minimum disclosure**

Open the privacy inspector and exact excerpt expander.

“Retrieval now runs locally. I can see the exact five-or-fewer excerpts that would cross the AI boundary. The full PDF and embeddings stay local.”

**1:20–1:38 — Consume, then AI**

Click **Consume one-time permission and ask AI**. Show the answer and page citation.

“PrivateDocs first finalizes a deterministic nullifier on Midnight. Only after the indexer confirms it does the Responses API receive the exact question and selected context, with request storage disabled.”

**1:38–1:50 — Replay protection**

Click **Verify replay protection**.

“A second consume is rejected. Retrying requires a fresh authorization opening and therefore a distinct authorization commitment.”

**1:50–2:00 — Revocation and value**

If recording time allows, authorize a second question and revoke the document; otherwise show the E2E test receipt/log.

“Revocation blocks every outstanding authorization for this document commitment. This turns AI data access into auditable, privacy-preserving consent.”

## Backup path

If proof generation is too slow for a continuous two-minute capture, record the authorization/consumption waits separately, then edit dead time only. Do not replace them with fabricated receipts. Keep the transaction IDs, block heights and real E2E terminal output visible long enough to read.

## Claims to avoid

- “The proof server sees nothing.”
- “The model can never retain data.”
- “The blockchain guarantees the Python process cannot be bypassed.”
- “This is production-ready compliance.”
- “The document is encrypted on-chain.”
