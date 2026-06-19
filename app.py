import streamlit as st

from utils.pdf_loader import (
    save_uploaded_file,
    extract_text_from_pdf
)

from utils.chunker import split_text_into_chunks

from utils.embeddings import (
    create_embeddings,
    create_query_embedding
)

from utils.vector_store import (
    create_faiss_index,
    search_faiss_index
)

st.set_page_config(
    page_title="AI Document Assistant",
    page_icon="📄",
    layout="wide"
)

st.title("📄 AI Document Assistant")
st.subheader("Upload a PDF and chat with your document")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"]
)

if uploaded_file:

    # Save PDF
    file_path = save_uploaded_file(uploaded_file)

    # Extract text
    text = extract_text_from_pdf(file_path)

    # Create chunks
    chunks = split_text_into_chunks(text)

    # Create embeddings
    embeddings = create_embeddings(chunks)

    # Create FAISS index
    faiss_index = create_faiss_index(embeddings)

    st.success(f"Uploaded: {uploaded_file.name}")

    st.write("### File Information")

    col1, col2 = st.columns(2)

    with col1:
        st.write("File Name:")
        st.write(uploaded_file.name)

    with col2:
        st.write("File Size:")
        st.write(f"{uploaded_file.size / 1024:.2f} KB")

    st.write("### Saved Location")
    st.code(file_path)

    st.write("### Chunk Information")
    st.write(f"Total Chunks Created: {len(chunks)}")

    st.write("### Embedding Information")
    st.write(f"Embedding Shape: {embeddings.shape}")

    st.write("### Vector Database")
    st.write(f"Vectors Stored: {faiss_index.ntotal}")

    # Question box
    st.write("### Ask a Question")

    query = st.text_input(
        "Enter your question"
    )

    if query:

        query_embedding = create_query_embedding(
            query
        )

        distances, indices = search_faiss_index(
            faiss_index,
            query_embedding,
            top_k=3
        )

        st.write("### Retrieved Chunks")

        for idx in indices[0]:
            st.write("---")
            st.write(chunks[idx])

    st.write("### First Chunk Preview")

    st.text_area(
        "Chunk 1",
        chunks[0],
        height=250
    )

    st.write("### Extracted Text Preview")

    st.text_area(
        "Document Text",
        text[:5000],
        height=300
    )