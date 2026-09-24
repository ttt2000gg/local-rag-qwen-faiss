from pathlib import Path

import faiss
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from ollama import embed, chat


# =========================
# Настройки
# =========================

DOCUMENTS_DIR = Path("docs")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen3:4b"

TOP_K = 3


# =========================
# FastAPI
# =========================

app = FastAPI(
    title="Local RAG API",
    description="Local RAG system with Qwen3, Ollama and FAISS",
)


# =========================
# Request model
# =========================

class Question(BaseModel):
    question: str


# =========================
# Chunking
# =========================

def split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()

    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        word_length = len(word) + 1

        if current_length + word_length > chunk_size:
            chunks.append(" ".join(current_chunk))

            overlap_words = []
            overlap_length = 0

            for previous_word in reversed(current_chunk):
                overlap_words.insert(0, previous_word)
                overlap_length += len(previous_word) + 1

                if overlap_length >= overlap:
                    break

            current_chunk = overlap_words
            current_length = sum(
                len(w) + 1 for w in current_chunk
            )

        current_chunk.append(word)
        current_length += word_length

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# =========================
# Embeddings
# =========================

def get_embedding(text):
    response = embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


# =========================
# Загрузка документов
# =========================

documents = []

files = list(DOCUMENTS_DIR.glob("*.txt"))

for file in files:
    text = file.read_text(encoding="utf-8")

    chunks = split_text(text)

    for chunk in chunks:
        documents.append({
            "source": file.name,
            "text": chunk,
        })


# =========================
# Создание FAISS индекса
# =========================

print(f"Файлов: {len(files)}")
print(f"Chunks: {len(documents)}")
print("Создаю embeddings...")

embeddings = []

for i, document in enumerate(documents, start=1):
    vector = get_embedding(document["text"])

    embeddings.append(vector)

    print(
        f"[{i}/{len(documents)}] "
        f"{document['source']}"
    )


embeddings = np.array(
    embeddings,
    dtype="float32",
)

# Нормализация для cosine similarity
faiss.normalize_L2(embeddings)

dimension = embeddings.shape[1]

index = faiss.IndexFlatIP(dimension)

index.add(embeddings)

print(f"Размерность embedding: {dimension}")
print(f"Документов в FAISS: {index.ntotal}")


# =========================
# RAG
# =========================

def ask_rag(query: str):

    # Embedding вопроса
    query_embedding = np.array(
        [get_embedding(query)],
        dtype="float32",
    )

    faiss.normalize_L2(query_embedding)

    # Поиск
    scores, indices = index.search(
        query_embedding,
        TOP_K,
    )

    # Формируем контекст
    context_parts = []

    sources = []

    for score, index_number in zip(
        scores[0],
        indices[0],
    ):

        document = documents[index_number]

        context_parts.append(
            f"""
Источник: {document["source"]}

{document["text"]}
"""
        )

        if document["source"] not in sources:
            sources.append(
                document["source"]
            )

    context = "\n".join(context_parts)

    # Prompt для LLM
    prompt = f"""
Ты — помощник, который отвечает
только на основе предоставленного контекста.

Если в контексте недостаточно информации
для ответа, честно скажи, что информации недостаточно.

Не придумывай факты, которых нет в контексте.

КОНТЕКСТ:

{context}

ВОПРОС:

{query}

Ответь на вопрос на русском языке.
"""

    # Qwen
    response = chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return {
        "answer": response.message.content,
        "sources": sources,
    }


# =========================
# API endpoints
# =========================

@app.get("/")
def root():
    return {
        "message": "Local RAG API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/ask")
def ask(data: Question):

    result = ask_rag(
        data.question
    )

    return result
