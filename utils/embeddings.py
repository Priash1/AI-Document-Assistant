# Embeddings will be added in Phase 4

from sentence_transformers import SentenceTransformer


def load_embedding_model():

    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    return model


def create_embeddings(chunks):

    model = load_embedding_model()

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True
    )

    return embeddings

def create_query_embedding(query):

    model = load_embedding_model()

    embedding = model.encode(
        [query],
        convert_to_numpy=True
    )

    return embedding