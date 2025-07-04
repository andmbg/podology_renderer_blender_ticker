FROM python:3.12-slim

WORKDIR /podology_renderer

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        build-essential \
        wget \
        ca-certificates \
        libgl1 \
        libxrender1 \
        libx11-6 \
        libxi6 \
        libsm6 \
        libegl1 \
        python3-poetry

# Download and install Blender 4.0.2
RUN wget https://download.blender.org/release/Blender4.0/blender-4.0.2-linux-x64.tar.xz && \
    tar -xf blender-4.0.2-linux-x64.tar.xz && \
    mv blender-4.0.2-linux-x64 /opt/blender && \
    ln -s /opt/blender/blender /usr/bin/blender && \
    rm blender-4.0.2-linux-x64.tar.xz

RUN apt-get install -y \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libosmesa6-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY .env .env
COPY podology_renderer ./podology_renderer
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
RUN poetry install --no-root --no-interaction --no-ansi

ENV LIBGL_ALWAYS_SOFTWARE=1
ENV PYOPENGL_PLATFORM=osmesa
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
RUN mkdir -p /tmp/runtime-root

CMD ["poetry", "run", "uvicorn", "podology_renderer.server:app", "--host", "0.0.0.0", "--port", "8002"]
