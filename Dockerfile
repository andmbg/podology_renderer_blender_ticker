FROM meihaiyi/blender:blender-4.3-cuda12.6.3-ubuntu24.04

WORKDIR /podology_renderer

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        build-essential \
        wget \
        ca-certificates \
        python3-poetry

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY .env .env
COPY podology_renderer ./podology_renderer
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry install --no-root --no-interaction --no-ansi

CMD ["poetry", "run", "uvicorn", "podology_renderer.server:app", "--host", "0.0.0.0", "--port", "8002"]
