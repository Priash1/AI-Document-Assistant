# AI Document Assistant

An AI-powered document assistant built with Python, Streamlit, FAISS, and Sentence Transformers.

## Features

- Upload PDF documents
- Extract text from PDFs
- Split documents into chunks
- Generate embeddings using Sentence Transformers
- Store vectors using FAISS
- Semantic document search
- Retrieve relevant document sections from user questions

## Tech Stack

- Python
- Streamlit
- PyMuPDF
- LangChain Text Splitters
- Sentence Transformers
- FAISS

## Project Structure

AI-DOCUMENT-ASSISTANT/

├── app.py

├── uploads/

├── vector_db/

├── data/

├── utils/

│ ├── pdf_loader.py

│ ├── chunker.py

│ ├── embeddings.py

│ ├── vector_store.py

│ └── chatbot.py

├── requirements.txt

├── README.md

└── .gitignore

## Installation

```bash
git clone <repository-url>
cd AI-DOCUMENT-ASSISTANT
pip install -r requirements.txt
streamlit run app.py