# syntax=docker/dockerfile:1

# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Current packaging tools (the base image ships ones with known CVEs).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the independent worker package first (path dependency).
COPY worker /worker
RUN uv pip install --system --no-cache /worker

COPY services/parser/pyproject.toml ./
COPY services/parser/README.md ./
COPY services/parser/app ./app
# OCR_ENGINE=paddleocr installs PaddleOCR (ONNX Runtime) and bakes its models in.
ARG OCR_ENGINE=tesseract
ENV OCR_ENGINE=${OCR_ENGINE}
RUN if [ "$OCR_ENGINE" = "paddleocr" ]; then \
        uv pip install --system --no-cache --no-sources ".[paddle]" huggingface_hub; \
    else \
        uv pip install --system --no-cache --no-sources .; \
    fi

# The official ONNX exports of PaddlePaddle, at pinned revisions and checked against their hashes.
ARG DET_MODEL_REVISION=e6f4fa85f00e168c862bc462aebca69eef9b3d3d
ARG DET_MODEL_SHA256=a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d
ARG REC_MODEL_REVISION=89d3a50e2c27e2e7cceeab0e944c25c807d5db4f
ARG REC_MODEL_SHA256=7888113072263cb471b93f66dd5e2ad70548dc526fa1ace760d0d973dd121498
ARG ORI_MODEL_REVISION=7330ab7039123e46af2dc03154b9969aa412c61d
RUN mkdir -p /models && if [ "$OCR_ENGINE" = "paddleocr" ]; then \
        python -c "\
from huggingface_hub import snapshot_download as d; \
d('PaddlePaddle/PP-OCRv5_mobile_det_onnx', revision='${DET_MODEL_REVISION}', local_dir='/models/PP-OCRv5_mobile_det_onnx', allow_patterns=['inference.onnx', 'inference.yml']); \
d('PaddlePaddle/latin_PP-OCRv5_mobile_rec_onnx', revision='${REC_MODEL_REVISION}', local_dir='/models/latin_PP-OCRv5_mobile_rec_onnx', allow_patterns=['inference.onnx', 'inference.yml']); \
d('PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx', revision='${ORI_MODEL_REVISION}', local_dir='/models/PP-LCNet_x1_0_doc_ori_onnx', allow_patterns=['inference.onnx', 'inference.yml'])" \
        && echo "${DET_MODEL_SHA256}  /models/PP-OCRv5_mobile_det_onnx/inference.onnx" | sha256sum -c - \
        && echo "${REC_MODEL_SHA256}  /models/latin_PP-OCRv5_mobile_rec_onnx/inference.onnx" | sha256sum -c - \
        && rm -rf /models/*/.cache; \
    fi

# Bake the Tesseract language data into the image (needs network at build time).
ARG OCR_LANGUAGE=eng+fra
ENV OCR_LANGUAGE=${OCR_LANGUAGE}
ENV HF_HOME=/opt/hf
RUN python -m app.warmup

FROM python:3.12-slim AS runtime
ARG OCR_ENGINE=tesseract
ENV OCR_ENGINE=${OCR_ENGINE}
# OpenCV (a dependency of PaddleOCR) loads these two at import.
RUN if [ "$OCR_ENGINE" = "paddleocr" ]; then \
        apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
        && rm -rf /var/lib/apt/lists/*; \
    fi
# pip is a build tool: the runtime image never installs anything, and the pip bundled with the base
# image carries known CVEs. Removed rather than upgraded, so there is nothing left to keep patched.
RUN python -m pip uninstall -y pip
RUN useradd --system --create-home --uid 10001 --home-dir /app app \
    && mkdir -p /opt/hf && chown -R app:app /app /opt/hf
COPY --from=builder --chown=app:app /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder --chown=app:app /usr/local/bin /usr/local/bin
COPY --from=builder --chown=app:app /app/app /app/app
COPY --from=builder --chown=app:app /models /models
# PaddleOCR keeps small working files in HOME and looks for no model hoster (the models are in the image).
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
# Tesseract traineddata is downloaded by warmup to /root/.tesseract-rs (not /opt/hf). The worker runs
# as `app` (HOME=/app), which can neither read /root nor look there: the data goes where LiteParse
# looks for it, ~/.tesseract-rs, or it would download it again at runtime.
COPY --from=builder --chown=app:app /root/.tesseract-rs /app/.tesseract-rs
USER app

HEALTHCHECK --interval=60s --timeout=20s --start-period=120s --retries=3 \
    CMD celery -A app.celery_app.celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
