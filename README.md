# Local RAG with Qwen, Ollama and FAISS

Простой локальный RAG-проект на Python.

Проект загружает текстовые документы, разбивает их на чанки, преобразует чанки в embeddings, ищет наиболее релевантные фрагменты с помощью FAISS и передаёт найденный контекст локальной LLM Qwen3:4b для генерации ответа.

## Архитектура

```text
TXT documents
      │
      ▼
   Chunking
      │
      ▼
Embedding model
nomic-embed-text
      │
      ▼
   Embeddings
      │
      ▼
     FAISS
      │
      │  пользовательский вопрос
      ▼
Top-K relevant chunks
      │
      ▼
    Context
      │
      ▼
   Qwen3:4b
      │
      ▼
  Answer + sources
