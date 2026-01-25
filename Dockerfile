# dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    libffi-dev \
    libssl-dev \
    gcc \
    python3-dev \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY etcd-encryption-sidecar.py encryption_plugin_system.py /app/

RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    etcd3 \
    flask==2.3.2 \
    pycryptodome==3.23.0 \
    "protobuf==3.20.*"

EXPOSE 8080

CMD ["python", "etcd_encryption_sidecar.py"]