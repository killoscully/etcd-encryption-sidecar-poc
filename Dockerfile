FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     netbase     && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel  && pip install --no-cache-dir     etcd3     flask==2.3.2     cryptography==42.0.8     "protobuf==3.20.*"

COPY encryption_plugin_system.py /app/encryption_plugin_system.py
COPY etcd_encryption_sidecar.py /app/etcd_encryption_sidecar.py

EXPOSE 5000

CMD ["python", "/app/etcd_encryption_sidecar.py"]
