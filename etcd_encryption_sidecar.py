import html as html_escape
import logging
import os
import time
import traceback

import etcd3
from etcd3 import exceptions as etcd_exceptions
from flask import Flask, Response, jsonify, request

from encryption_plugin_system import default_manager, ensure_rsa_key_material, load_key_material_from_env, try_decrypt_any

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("etcd_sidecar")

ETCD_HOST = os.environ.get("ETCD_HOST", "127.0.0.1")
ETCD_PORT = int(os.environ.get("ETCD_PORT", "2379"))
ETCD_RETRIES = int(os.environ.get("ETCD_RETRIES", "12"))
ETCD_RETRY_DELAY = float(os.environ.get("ETCD_RETRY_DELAY", "2.0"))
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
ENCRYPTION_TYPE = os.environ.get("ENCRYPTION_TYPE", "PLAINTEXT").strip().upper()

plugin_manager = default_manager()
key_material = ensure_rsa_key_material(load_key_material_from_env("ENCRYPTION_KEY_DATA"))
_etcd_client = None


def connect_etcd():
    last_exc = None
    for attempt in range(1, ETCD_RETRIES + 1):
        try:
            client = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
            client.status()
            logger.info("Connected to etcd at %s:%d (attempt %d)", ETCD_HOST, ETCD_PORT, attempt)
            return client
        except Exception as exc:
            last_exc = exc
            logger.warning("etcd connect attempt %d failed: %s", attempt, exc)
            time.sleep(ETCD_RETRY_DELAY)
    raise last_exc


def _reset_etcd_client():
    global _etcd_client
    try:
        if _etcd_client:
            _etcd_client.close()
    except Exception:
        pass
    _etcd_client = None


def get_etcd_client():
    global _etcd_client
    if _etcd_client is None:
        _etcd_client = connect_etcd()
    return _etcd_client


def safe_etcd_call(fn, *args, **kwargs):
    try:
        client = get_etcd_client()
        return fn(client, *args, **kwargs)
    except (etcd_exceptions.ConnectionFailedError, ConnectionError, OSError) as exc:
        logger.warning("etcd call failed, attempting reconnect: %s", exc)
        _reset_etcd_client()
        client = get_etcd_client()
        return fn(client, *args, **kwargs)


def decode_value(value):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def get_value(key_name):
    return safe_etcd_call(lambda client, key: client.get(key), key_name)


def put_value(key_name, value):
    return safe_etcd_call(lambda client, key, val: client.put(key, val), key_name, value)


app = Flask(__name__)


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({
        "ok": True,
        "encryption_type": ENCRYPTION_TYPE,
        "supported_algorithms": plugin_manager.names,
        "etcd": f"{ETCD_HOST}:{ETCD_PORT}",
    }), 200


@app.route("/put", methods=["POST"])
def put_handler():
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({"error": "invalid JSON body"}), 400
        key = data.get("key")
        value = data.get("value")
        if not key or value is None:
            return jsonify({"error": "missing key or value"}), 400
        plugin = plugin_manager.get(ENCRYPTION_TYPE)
        started = time.perf_counter()
        ciphertext = plugin.encrypt(str(value), key_material)
        crypto_ms = (time.perf_counter() - started) * 1000.0
        put_value(key, ciphertext)
        return jsonify({"result": "ok", "alg": plugin.name, "key": key, "crypto_ms": round(crypto_ms, 3)}), 200
    except KeyError as exc:
        logger.error("Unsupported encryption type: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("PUT handler error: %s\n%s", exc, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500


@app.route("/get", methods=["GET"])
def get_handler():
    try:
        key = request.args.get("key")
        if not key:
            return jsonify({"error": "missing key parameter"}), 400
        raw_value, _meta = get_value(key)
        if raw_value is None:
            return jsonify({"found": False, "value": None}), 200
        stored = decode_value(raw_value)
        started = time.perf_counter()
        plaintext = try_decrypt_any(str(stored), key_material, plugin_manager)
        crypto_ms = (time.perf_counter() - started) * 1000.0
        return jsonify({"found": True, "value": plaintext, "key": key, "crypto_ms": round(crypto_ms, 3)}), 200
    except Exception as exc:
        logger.exception("GET handler error: %s\n%s", exc, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500


@app.route("/all", methods=["GET"])
def all_handler():
    prefix = request.args.get("prefix", "")
    pref_bytes = prefix.encode("utf-8") if prefix else None

    def _list(client, p):
        items = []
        iterator = client.get_prefix(p) if p else client.get_all()
        for value, meta in iterator:
            k = getattr(meta, "key", b"")
            if isinstance(k, (bytes, bytearray)):
                k = k.decode("utf-8", errors="replace")
            stored = decode_value(value)
            try:
                decoded = try_decrypt_any(str(stored), key_material, plugin_manager)
            except Exception:
                decoded = str(stored)
            items.append({"key": k, "value": decoded})
        return items

    try:
        items = safe_etcd_call(_list, pref_bytes)
    except Exception as exc:
        logger.exception("ALL handler error: %s\n%s", exc, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500

    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        rows = "".join(
            "<tr><td>{}</td><td>{}</td></tr>".format(html_escape.escape(item["key"] or ""), html_escape.escape(str(item["value"] or "")))
            for item in items
        )
        html_page = (
            "<!doctype html><html><head><meta charset='utf-8'><title>etcd keys</title></head>"
            f"<body><h1>Keys (prefix={html_escape.escape(prefix)})</h1><table border='1'>"
            "<tr><th>Key</th><th>Value</th></tr>"
            f"{rows}</table></body></html>"
        )
        return Response(html_page, mimetype="text/html")
    return jsonify({"count": len(items), "items": items}), 200


if __name__ == "__main__":
    logger.info("Starting sidecar on %s:%d, etcd=%s:%d, encryption_type=%s", FLASK_HOST, FLASK_PORT, ETCD_HOST, ETCD_PORT, ENCRYPTION_TYPE)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
