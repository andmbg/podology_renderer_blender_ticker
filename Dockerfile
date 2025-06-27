FROM linuxserver/blender:latest

WORKDIR /podology_renderer

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    python3-pip \
    python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements.txt ./
COPY .env .env
COPY podology_renderer ./podology_renderer

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "podology_renderer.server:app", "--host", "0.0.0.0", "--port", "8002"]