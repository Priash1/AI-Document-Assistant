"""PrivateDocs AI: proof-gated, in-memory document question answering."""

from __future__ import annotations

import os
from pathlib import PurePath
from typing import Any

import streamlit as st

from utils.chatbot import (
    ChatAnswer,
    ChatbotError,
    answer_question,
    prepare_context,
)
from utils.chunker import DocumentChunk, split_document_into_chunks
from utils.embeddings import EmbeddingError, create_embeddings, create_query_embedding
from utils.pdf_loader import ExtractedPDF, PDFProcessingError, extract_pdf_from_bytes
from utils.privacy import (
    MidnightBridgeClient,
    MidnightReceipt,
    PermissionPhase,
    PermissionState,
    PrivacyError,
    canonicalize_question,
    document_digest,
    query_digest,
)
from utils.vector_store import (
    SearchResult,
    VectorStore,
    VectorStoreError,
    create_vector_store,
    search_vector_store,
)

APP_TITLE = "PrivateDocs AI"
MAX_UPLOAD_MB = 20
TOP_K = 5


st.set_page_config(
    page_title=f"{APP_TITLE} · Midnight",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    :root {
        --ink: #edf5ff;
        --muted: #9eb0c7;
        --panel: rgba(13, 23, 42, .82);
        --line: rgba(147, 176, 216, .18);
        --cyan: #5ce1e6;
        --violet: #9b8cff;
        --green: #4ee0a0;
        --amber: #ffc96b;
    }
    .stApp {
        background:
          radial-gradient(circle at 8% 0%, rgba(71, 83, 190, .25), transparent 34rem),
          radial-gradient(circle at 92% 12%, rgba(0, 191, 198, .13), transparent 30rem),
          #07101d;
        color: var(--ink);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: rgba(7, 16, 29, .94);
        border-right: 1px solid var(--line);
    }
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stWidgetLabel"] p,
    .stApp [data-testid="stCaptionContainer"] p,
    .stApp [data-testid="stFileUploaderDropzoneInstructions"] div,
    .stApp [data-testid="stFileUploaderDropzoneInstructions"] small {
        color: var(--muted);
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    [data-testid="stSidebar"] strong { color: var(--ink); }
    .block-container { max-width: 1240px; padding-top: 2rem; }
    .hero {
        padding: 2.1rem 2.2rem;
        border: 1px solid var(--line);
        border-radius: 24px;
        background: linear-gradient(125deg, rgba(25, 42, 72, .92), rgba(11, 21, 39, .82));
        box-shadow: 0 24px 80px rgba(0, 0, 0, .28);
        margin-bottom: 1.25rem;
    }
    .eyebrow {
        color: var(--cyan); font-size: .76rem; font-weight: 750;
        letter-spacing: .16em; text-transform: uppercase; margin-bottom: .65rem;
    }
    .hero h1 { font-size: clamp(2.2rem, 5vw, 4.2rem); line-height: .98; margin: 0; }
    .hero p { color: var(--muted); font-size: 1.08rem; max-width: 760px; margin: 1rem 0 0; }
    .proof-pill {
        display: inline-flex; align-items: center; gap: .45rem; margin-top: 1.1rem;
        padding: .48rem .8rem; border-radius: 999px;
        background: rgba(78, 224, 160, .09); border: 1px solid rgba(78, 224, 160, .28);
        color: #8ff0bf; font-size: .82rem; font-weight: 650;
    }
    .step-card, .metric-card, .privacy-card {
        border: 1px solid var(--line); border-radius: 17px; padding: 1rem 1.05rem;
        background: var(--panel); min-height: 100%;
    }
    .step-number { color: var(--violet); font-size: .72rem; font-weight: 800; letter-spacing: .12em; }
    .step-title { font-size: 1rem; font-weight: 720; margin: .25rem 0; }
    .step-copy, .micro { color: var(--muted); font-size: .84rem; line-height: 1.45; }
    .metric-value { font-size: 1.28rem; font-weight: 760; overflow-wrap: anywhere; }
    .metric-label {
        color: var(--muted); font-size: .74rem;
        text-transform: uppercase; letter-spacing: .08em;
    }
    .privacy-card h4 { margin: 0 0 .35rem; }
    .privacy-card.allowed { border-color: rgba(78, 224, 160, .28); }
    .privacy-card.blocked { border-color: rgba(255, 201, 107, .25); }
    .receipt {
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        color: #b8c9dd; font-size: .78rem; overflow-wrap: anywhere;
    }
    div[data-testid="stFileUploader"] section {
        border: 1px dashed rgba(92, 225, 230, .48); border-radius: 16px;
        background: rgba(92, 225, 230, .035);
    }
    div[data-testid="stFileUploader"] section div,
    div[data-testid="stFileUploader"] section span,
    div[data-testid="stFileUploader"] section small {
        color: var(--muted) !important;
    }
    div[data-testid="stFileUploader"] section button,
    div[data-testid="stFileUploader"] section button * {
        color: #17243a !important;
    }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 11px; font-weight: 680;
    }
    .footer-note { color: var(--muted); text-align: center; font-size: .78rem; margin-top: 2.5rem; }
</style>
""",
    unsafe_allow_html=True,
)


def _initial_state() -> None:
    defaults: dict[str, Any] = {
        "document_key": None,
        "document_name": None,
        "document": None,
        "chunks": None,
        "vector_store": None,
        "permission": None,
        "retrieval_key": None,
        "results": None,
        "answer": None,
        "answer_question": None,
        "notice": None,
        "upload_epoch": 0,
        "question_epoch": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_document() -> None:
    for key in (
        "document_key",
        "document_name",
        "document",
        "chunks",
        "vector_store",
        "permission",
        "retrieval_key",
        "results",
        "answer",
        "answer_question",
        "notice",
    ):
        st.session_state[key] = None


def _safe_name(name: str) -> str:
    return PurePath(name.replace("\\", "/")).name[:180] or "document.pdf"


def _process_upload(uploaded_file: Any) -> bool:
    raw_pdf = uploaded_file.getvalue()
    digest = document_digest(raw_pdf)
    if digest == st.session_state.document_key:
        return False

    document = extract_pdf_from_bytes(raw_pdf)
    chunks = split_document_into_chunks(document)
    _reset_document()
    st.session_state.question_epoch += 1
    st.session_state.document_key = digest
    st.session_state.document_name = _safe_name(uploaded_file.name)
    st.session_state.document = document
    st.session_state.chunks = chunks
    st.session_state.permission = PermissionState(document_digest=digest)
    st.session_state.notice = "PDF validated and parsed in memory. Nothing was written to disk."
    return True


def _api_key() -> str | None:
    environment_key = os.getenv("OPENAI_API_KEY")
    if environment_key and environment_key.strip():
        return environment_key.strip()
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        secret_key = None
    return secret_key.strip() if isinstance(secret_key, str) and secret_key.strip() else None


def _bridge() -> MidnightBridgeClient:
    return MidnightBridgeClient()


def _short(value: str | None, size: int = 13) -> str:
    if not value:
        return "—"
    return f"{value[:size]}…{value[-6:]}"


def _authorize_exact_query(question: str) -> None:
    permission: PermissionState = st.session_state.permission
    digest = query_digest(question)
    bridge = _bridge()
    bridge.health()

    if permission.phase is PermissionPhase.UPLOADED:
        permission.record_registration(
            bridge.register_document(permission.document_digest)
        )
    permission.record_authorization(
        digest,
        bridge.authorize_query(permission.document_digest, digest),
    )
    st.session_state.vector_store = None
    st.session_state.retrieval_key = None
    st.session_state.results = None
    st.session_state.answer = None
    st.session_state.answer_question = None


def _retrieve_authorized_context(question: str) -> list[SearchResult]:
    permission: PermissionState = st.session_state.permission
    digest = query_digest(question)
    permission.require_authorized(digest)

    if st.session_state.vector_store is None:
        chunks: list[DocumentChunk] = st.session_state.chunks
        st.session_state.vector_store = create_vector_store(
            create_embeddings(chunks),
            chunks,
        )
    if st.session_state.retrieval_key != digest:
        store: VectorStore = st.session_state.vector_store
        results = search_vector_store(
            store,
            create_query_embedding(question),
            top_k=TOP_K,
        )
        if not results:
            raise VectorStoreError("No relevant authorized excerpts were found.")
        st.session_state.results = results
        st.session_state.retrieval_key = digest
    return st.session_state.results


def _consume_and_answer(question: str) -> ChatAnswer:
    key = _api_key()
    if not key:
        raise ChatbotError(
            "OPENAI_API_KEY is missing. The one-time permission was not consumed."
        )

    results = _retrieve_authorized_context(question)
    permission: PermissionState = st.session_state.permission
    digest = query_digest(question)
    consumption = _bridge().consume_query(permission.document_digest, digest)
    permission.record_consumption(digest, consumption)

    # The provider call happens only after finalized, indexer-verified consumption.
    return answer_question(question, results, api_key=key)


def _revoke() -> None:
    permission: PermissionState = st.session_state.permission
    receipt = _bridge().revoke_document(permission.document_digest)
    permission.record_revocation(receipt)
    st.session_state.vector_store = None
    st.session_state.results = None
    st.session_state.retrieval_key = None
    st.session_state.answer = None
    st.session_state.answer_question = None


def _render_receipt(receipt: MidnightReceipt) -> None:
    st.markdown(
        f"""
<div class="step-card">
  <div class="step-number">{receipt.operation.upper()} · FINALIZED</div>
  <div class="receipt">network: {receipt.network}<br>
  contract: {receipt.contract_address}<br>
  tx: {receipt.tx_id}<br>
  block: {receipt.block_height}<br>
  document commitment: {receipt.document_commitment or '—'}<br>
  authorization commitment: {receipt.authorization_commitment or '—'}<br>
  nullifier: {receipt.nullifier or '—'}<br>
  indexer verified: {str(receipt.ledger_verified).lower()}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_privacy_inspector(results: list[SearchResult] | None, question: str) -> None:
    st.subheader("Privacy inspector")
    columns = st.columns(4)
    cards = (
        (
            "App memory",
            "PDF bytes, extracted text, local embeddings and your question. "
            "Upload bytes are not persisted by this app.",
            "allowed",
        ),
        (
            "Midnight proof server",
            "Private digest witnesses/openings needed to prove the circuit. It never receives the PDF text.",
            "allowed",
        ),
        (
            "Midnight ledger",
            "Commitments, nullifiers and contract state—not the document, question or retrieved excerpts.",
            "allowed",
        ),
        (
            "OpenAI",
            (
                f"Exact question plus {len(results)} selected excerpts only; request storage is disabled."
                if results
                else "Nothing yet. The provider call remains blocked until finalized one-time consumption."
            ),
            "allowed" if results else "blocked",
        ),
    )
    for column, (title, copy, css_class) in zip(columns, cards, strict=True):
        column.markdown(
            f'<div class="privacy-card {css_class}"><h4>{title}</h4><div class="micro">{copy}</div></div>',
            unsafe_allow_html=True,
        )

    if results:
        prepared = prepare_context(question, results)
        st.caption(
            f"Provider payload preview · {prepared.excerpt_count} excerpts · "
            f"{prepared.content_characters:,} document characters · pages "
            + ", ".join(str(page) for page in prepared.source_pages)
        )
        with st.expander("Inspect the exact document excerpts selected for the provider"):
            for result in results:
                st.markdown(
                    f"**Excerpt {result.rank} · {result.chunk.source_label} · similarity {result.score:.3f}**"
                )
                st.text(result.chunk.text)


_initial_state()

st.markdown(
    """
<section class="hero">
  <div class="eyebrow">Midnight · Zero-knowledge access control</div>
  <h1>PrivateDocs <span style="color:#5ce1e6">AI</span></h1>
  <p>Ask sensitive PDFs a question only after Midnight authorizes that exact
  document–query pair. The one-time permission is consumed on-ledger before any
  excerpt can cross the AI boundary.</p>
  <div class="proof-pill">● Fail-closed · finalized proof required</div>
</section>
""",
    unsafe_allow_html=True,
)

flow_columns = st.columns(4)
for column, (number, title, copy) in zip(
    flow_columns,
    (
        ("01", "Upload privately", "Validate and parse the PDF only in application memory."),
        ("02", "Bind exact intent", "Commit to domain-separated document and query digests."),
        ("03", "Prove permission", "Wait for a real finalized Midnight authorization transition."),
        ("04", "Consume, then ask", "Nullify the one-time permit before sending selected context."),
    ),
    strict=True,
):
    column.markdown(
        f'<div class="step-card"><div class="step-number">{number}</div>'
        f'<div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>',
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.markdown("### Proof console")
    permission: PermissionState | None = st.session_state.permission
    phase = permission.phase.value if permission else "waiting for PDF"
    st.caption("Current gate")
    st.markdown(f"**{phase.upper()}**")
    st.caption("Bridge")
    st.code(os.getenv("PRIVATEDOCS_MIDNIGHT_BRIDGE_URL", "http://127.0.0.1:8787"), language=None)
    if st.button("Check real Midnight stack", use_container_width=True):
        try:
            health = _bridge().health()
            st.success(
                f"Ready · {health.get('network', 'Midnight')} · no simulation"
            )
        except PrivacyError as exc:
            st.error(str(exc))

    if permission:
        st.divider()
        st.caption("Private document digest")
        st.code(permission.document_digest, language=None)
        st.caption("This digest is not the raw file and is never used as an encryption key.")
        if permission.receipts:
            st.caption(f"Verified ledger transitions · {len(permission.receipts)}")
            for receipt in reversed(permission.receipts):
                st.markdown(
                    f"`{receipt.operation}` · block {receipt.block_height} · `{_short(receipt.tx_id)}`"
                )
    st.divider()
    st.caption(
        "Prototype boundary: this app proves and records permission state. "
        "It does not make a claim about model correctness, endpoint compromise, "
        "or provider retention beyond the configured no-store request."
    )

st.markdown("## 1 · Load a confidential PDF")
uploaded = st.file_uploader(
    "Choose a text-based PDF",
    type=("pdf",),
    accept_multiple_files=False,
    key=f"pdf_upload_{st.session_state.upload_epoch}",
    help=f"Maximum {MAX_UPLOAD_MB} MB and 200 pages. The application does not save the upload.",
)

if uploaded is not None:
    try:
        if _process_upload(uploaded):
            st.rerun()
    except (PDFProcessingError, ValueError, TypeError) as exc:
        _reset_document()
        st.error(str(exc))

document: ExtractedPDF | None = st.session_state.document
permission = st.session_state.permission

if document and permission:
    if st.session_state.notice:
        st.success(st.session_state.notice)
        st.session_state.notice = None

    metrics = st.columns(4)
    values = (
        (st.session_state.document_name, "Document"),
        (f"{document.page_count}", "Pages"),
        (f"{len(st.session_state.chunks)}", "Local chunks"),
        (_short(permission.document_digest), "Private digest"),
    )
    for column, (value, label) in zip(metrics, values, strict=True):
        column.markdown(
            f'<div class="metric-card"><div class="metric-value">{value}</div>'
            f'<div class="metric-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([3, 1])
    with right:
        if st.button("Clear from memory", use_container_width=True):
            _reset_document()
            st.session_state.upload_epoch += 1
            st.session_state.question_epoch += 1
            st.rerun()

    st.markdown("## 2 · Authorize one exact question")
    locked = permission.phase is PermissionPhase.AUTHORIZED
    question = st.text_area(
        "Question",
        key=f"question_{st.session_state.question_epoch}",
        placeholder="What obligations survive termination?",
        height=100,
        max_chars=2_000,
        disabled=locked,
        help="Case, punctuation and internal spacing are binding. The field locks after authorization.",
    )

    if locked and permission.authorized_query_digest:
        st.info(
            "The authorized question is locked until its one-time permission "
            "is consumed or the document is revoked."
        )

    canonical_question = ""
    current_query_digest = None
    if question.strip():
        try:
            canonical_question = canonicalize_question(question)
            current_query_digest = query_digest(canonical_question)
            st.caption(f"Exact query digest · `{current_query_digest}`")
        except ValueError as exc:
            st.warning(str(exc))

    authorize_disabled = (
        not canonical_question
        or permission.phase in {PermissionPhase.AUTHORIZED, PermissionPhase.REVOKED}
    )
    authorize_col, revoke_col = st.columns([2, 1])
    with authorize_col:
        if st.button(
            "Generate and finalize Midnight authorization",
            type="primary",
            use_container_width=True,
            disabled=authorize_disabled,
        ):
            try:
                with st.spinner("Proving, submitting and verifying finalized ledger state…"):
                    _authorize_exact_query(canonical_question)
                st.success("This exact document–query pair now has one active permission.")
                st.rerun()
            except PrivacyError as exc:
                st.error(f"Authorization blocked: {exc}")
            except Exception:
                st.error("Authorization failed safely; no AI request was made.")
    with revoke_col:
        can_revoke = permission.phase not in {
            PermissionPhase.UPLOADED,
            PermissionPhase.REVOKED,
        }
        if st.button(
            "Revoke document",
            use_container_width=True,
            disabled=not can_revoke,
        ):
            try:
                with st.spinner("Finalizing revocation…"):
                    _revoke()
                st.success("Document permission was revoked on Midnight.")
                st.rerun()
            except PrivacyError as exc:
                st.error(f"Revocation failed safely: {exc}")

    if permission.phase is PermissionPhase.AUTHORIZED and question.strip():
        st.markdown("## 3 · Review the AI boundary, then consume")
        try:
            with st.spinner("Embedding and retrieving locally after authorization…"):
                authorized_results = _retrieve_authorized_context(canonical_question)
            _render_privacy_inspector(authorized_results, canonical_question)
        except (EmbeddingError, VectorStoreError, PrivacyError, ValueError) as exc:
            authorized_results = None
            st.error(f"Local retrieval failed; permission remains unconsumed: {exc}")

        if authorized_results:
            st.warning(
                "Submitting will first consume the one-time permission on Midnight. "
                "If the subsequent AI provider call fails, authorize a new permission to retry."
            )
            if not _api_key():
                st.info("Add OPENAI_API_KEY to the runtime environment. Until then, consumption is disabled.")
            if st.button(
                "Consume one-time permission and ask AI",
                type="primary",
                use_container_width=True,
                disabled=not bool(_api_key()),
            ):
                try:
                    with st.spinner("Consuming on-ledger, then requesting a grounded answer…"):
                        generated = _consume_and_answer(canonical_question)
                    st.session_state.answer = generated
                    st.session_state.answer_question = canonical_question
                    st.rerun()
                except ChatbotError as exc:
                    st.error(str(exc))
                except PrivacyError as exc:
                    st.error(f"AI access remained blocked: {exc}")
                except Exception:
                    st.error("The request failed safely. No hidden document data is displayed.")
    elif permission.phase in {PermissionPhase.UPLOADED, PermissionPhase.REGISTERED}:
        st.markdown("## 3 · AI boundary is closed")
        _render_privacy_inspector(None, canonical_question)
        st.warning(
            "No finalized authorization exists for this exact query. "
            "Retrieval and AI access are blocked."
        )
    elif permission.phase is PermissionPhase.REVOKED:
        st.error(
            "This document commitment is permanently revoked in the current contract deployment. "
            "A new deployment is required to create a separate lifecycle for the same PDF."
        )

    answer: ChatAnswer | None = st.session_state.answer
    if answer:
        st.markdown("## Grounded answer")
        st.success("One-time permission consumed · replay now blocked")
        st.markdown(answer.text)
        citation_text = (
            ", ".join(f"p. {page}" for page in answer.cited_pages)
            or "insufficient context response"
        )
        st.caption(
            f"Model: {answer.model} · Evidence: {citation_text} · "
            f"{answer.excerpt_count} authorized excerpts · request storage disabled"
        )
        if st.button("Verify replay protection", use_container_width=False):
            try:
                _bridge().consume_query(
                    permission.document_digest,
                    query_digest(st.session_state.answer_question),
                )
            except PrivacyError:
                st.success("Replay rejected: the consumed nullifier cannot be used again.")
            else:
                st.error("Unexpected replay acceptance. Do not treat this deployment as secure.")

    if permission.receipts:
        st.markdown("## Verifiable proof receipts")
        for verified_receipt in permission.receipts:
            _render_receipt(verified_receipt)
else:
    st.info("Upload a PDF to begin. Until then, no document or query leaves the browser session.")

st.markdown(
    '<div class="footer-note">PrivateDocs AI · Integrate Midnight Hackathon · '
    "real proofs only, no simulated authorization path</div>",
    unsafe_allow_html=True,
)
