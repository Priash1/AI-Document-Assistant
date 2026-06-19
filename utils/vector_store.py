import faiss
import numpy as np


def create_faiss_index(embeddings):

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(
        np.array(embeddings).astype("float32")
    )

    return index

def search_faiss_index(
    index,
    query_embedding,
    top_k=3
):

    distances, indices = index.search(
        query_embedding.astype("float32"),
        top_k
    )

    return distances, indices