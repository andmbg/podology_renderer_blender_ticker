FROM python:3.12-slim

WORKDIR /podology_renderer

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        build-essential \
        python3-poetry \
        blender && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY .env .env
COPY podology_renderer ./podology_renderer
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
RUN poetry install --no-root --no-interaction --no-ansi

CMD ["poetry", "run", "uvicorn", "podology_renderer.server:app", "--host", "0.0.0.0", "--port", "8002"]
