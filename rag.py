from pathlib import Path

from ollama import embed, chat

import faiss
import numpy as np


# ============================================================
# НАСТРОЙКИ
# ============================================================

DOCUMENTS_DIR = Path("docs")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen3:4b"

TOP_K = 3


# ============================================================
# 1. РАЗБИЕНИЕ ТЕКСТА НА CHUNKS
# ============================================================

def split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()

    chunks = []

    current_chunk = []
    current_length = 0

    for word in words:
        word_length = len(word) + 1

        if current_length + word_length > chunk_size:

            chunks.append(" ".join(current_chunk))

            # Сохраняем последние слова предыдущего chunk
            # для overlap
            overlap_words = []
            overlap_length = 0

            for previous_word in reversed(current_chunk):
                overlap_words.insert(0, previous_word)
                overlap_length += len(previous_word) + 1

                if overlap_length >= overlap:
                    break

            current_chunk = overlap_words

            current_length = sum(
                len(word) + 1
                for word in current_chunk
            )

        current_chunk.append(word)
        current_length += word_length

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ============================================================
# 2. EMBEDDING
# ============================================================

def get_embedding(text):
    response = embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


# ============================================================
# 3. ЗАГРУЗКА ДОКУМЕНТОВ
# ============================================================

documents = []

files = list(DOCUMENTS_DIR.glob("*.txt"))

print(f"Файлов найдено: {len(files)}")

for file_path in files:

    text = file_path.read_text(encoding="utf-8")

    chunks = split_text(text)

    for chunk in chunks:

        documents.append({
            "text": chunk,
            "source": file_path.name,
        })


print(f"Всего chunks: {len(documents)}")


# ============================================================
# 4. СОЗДАНИЕ EMBEDDINGS
# ============================================================

print("\nСоздаю embeddings...\n")

embeddings = []

for i, document in enumerate(documents):

    print(
        f"[{i + 1}/{len(documents)}] "
        f"{document['source']}"
    )

    embedding = get_embedding(
        document["text"]
    )

    embeddings.append(embedding)


# ============================================================
# 5. EMBEDDINGS → NUMPY
# ============================================================

embeddings = np.array(
    embeddings,
    dtype="float32"
)


# ============================================================
# 6. НОРМАЛИЗАЦИЯ ВЕКТОРОВ
# ============================================================

faiss.normalize_L2(embeddings)


# ============================================================
# 7. СОЗДАНИЕ FAISS INDEX
# ============================================================

dimension = embeddings.shape[1]

index = faiss.IndexFlatIP(dimension)

index.add(embeddings)

print("\n" + "=" * 70)
print(f"Размерность embedding: {dimension}")
print(f"Документов в FAISS: {index.ntotal}")
print("=" * 70)


# ============================================================
# 8. ПОЛУЧАЕМ ВОПРОС
# ============================================================

query = input("\nВведите вопрос: ")


# ============================================================
# 9. EMBEDDING ВОПРОСА
# ============================================================

query_embedding = get_embedding(query)

query_embedding = np.array(
    [query_embedding],
    dtype="float32"
)

faiss.normalize_L2(query_embedding)


# ============================================================
# 10. ПОИСК TOP-K
# ============================================================

scores, indices = index.search(
    query_embedding,
    TOP_K
)


# ============================================================
# 11. СОБИРАЕМ КОНТЕКСТ
# ============================================================

context_parts = []

for rank, (score, index_number) in enumerate(
    zip(scores[0], indices[0]),
    start=1
):

    document = documents[index_number]

    context_parts.append(
        f"""
Источник: {document['source']}
Фрагмент {rank}:
{document['text']}
"""
    )


context = "\n".join(context_parts)


# ============================================================
# 12. ПОКАЗЫВАЕМ НАЙДЕННЫЕ ДОКУМЕНТЫ
# ============================================================

print("\n" + "=" * 70)
print("НАЙДЕННЫЙ КОНТЕКСТ")
print("=" * 70)

for rank, (score, index_number) in enumerate(
    zip(scores[0], indices[0]),
    start=1
):

    document = documents[index_number]

    print(f"\n#{rank}")
    print(f"Сходство: {score:.4f}")
    print(f"Источник: {document['source']}")
    print(f"Текст:")
    print(document["text"])


# ============================================================
# 13. ПЕРЕДАЁМ КОНТЕКСТ QWEN
# ============================================================

prompt = f"""
Ты — помощник, который отвечает на вопросы
только на основе предоставленного контекста.

Если в контексте недостаточно информации для ответа,
честно скажи, что информации недостаточно.

Не придумывай факты, которых нет в контексте.

КОНТЕКСТ:
{context}

ВОПРОС:
{query}

Ответь на вопрос на русском языке.
"""


print("\n" + "=" * 70)
print("ОТВЕТ QWEN")
print("=" * 70)


# ============================================================
# 14. ЗАПРОС К QWEN
# ============================================================

response = chat(
    model=LLM_MODEL,
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
)


# ============================================================
# 15. ВЫВОД ОТВЕТА
# ============================================================

print(response.message.content)


# ============================================================
# 16. ИСТОЧНИКИ
# ============================================================

print("\n" + "=" * 70)
print("ИСТОЧНИКИ")
print("=" * 70)

used_sources = []

for index_number in indices[0]:

    source = documents[index_number]["source"]

    if source not in used_sources:
        used_sources.append(source)

for source in used_sources:
    print(f"- {source}")
