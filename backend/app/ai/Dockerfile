# RAG assistant: FastAPI /ask + bge-m3 embeddings; Qdrant and Ollama run as separate services.
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/models
WORKDIR /rag
RUN pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY *.py ./
COPY knowledge_base ./knowledge_base
EXPOSE 8090
CMD ["python", "start.py"]
