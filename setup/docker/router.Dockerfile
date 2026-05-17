FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3 \
        python3-yaml \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY src/collab_router.py /opt/collab-router/collab_router.py

EXPOSE 8090

CMD ["python3", "/opt/collab-router/collab_router.py"]
