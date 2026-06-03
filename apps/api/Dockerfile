# FastAPI Lambda image. Build from the repo root:
#   docker build -f apps/api/Dockerfile .
FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/var/task/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/var/task/.cache/sentence-transformers

WORKDIR ${LAMBDA_TASK_ROOT}

COPY packages/shared ./packages/shared
COPY packages/graph ./packages/graph
COPY apps/api ./apps/api

RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install ./packages/shared ./packages/graph ./apps/api

RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"

CMD ["api.main.handler"]
