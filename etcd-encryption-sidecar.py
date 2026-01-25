# python
import os
import time
import logging
import traceback
import html as html_escape

from flask import Flask, request, jsonify, Response
import etcd3
from etcd3 import exceptions as etcd_exceptions

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("etcd_sidecar")

# Configuration
ETCD_HOST = os.environ.get("ETCD_HOST", "127.0.0.1")
ETCD_PORT = int(os.environ.get("ETCD_PORT", "2379"))
ETCD_RETRIES = int(os.environ.get("ETCD_RETRIES", "12"))
ETCD_RETRY_DELAY = float(os.environ.get("ETCD_RETRY_DELAY", "2.0"))
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))

# Global client holder
_etcd_client = None

def connect_etcd():
    last_exc = None
    for attempt in range(1, ETCD_RETRIES + 1):
        try:
            client = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
            client.status()  # quick health check, will raise if unreachable
            logger.info("Connected to etcd at %s:%d (attempt %d)", ETCD_HOST, ETCD_PORT, attempt)
            return client
        except Exception as exc:
            last_exc = exc
            logger.warning("etcd connect attempt %d failed: %s", attempt, exc)
            time.sleep(ETCD_RETRY_DELAY)
    logger.error("Failed to connect to etcd after %d attempts", ETCD_RETRIES)
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
    """
    Call an etcd operation, retrying once by reconnecting on connection failure.
    fn: callable(client, *args, **kwargs)
    """
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
        try:
            return value.decode("utf-8")
        except Exception:
            return value.decode("latin-1", errors="replace")
    return value

def get_value(key_name):
    def _get(client, key):
        return client.get(key)
    raw_value, meta = safe_etcd_call(_get, key_name)
    return raw_value, meta

def put_value(key_name, value):
    def _put(client, key, val):
        return client.put(key, val)
    return safe_etcd_call(_put, key_name, value)

app = Flask(__name__)

@app.errorhandler(500)
def internal_error(e):
    # Ensure JSON is returned for unexpected errors
    logger.exception("Unhandled exception: %s", e)
    return jsonify({"error": "internal server error"}), 500

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

        put_value(key, value)
        return jsonify({"result": "ok"}), 200
    except Exception as e:
        logger.exception("PUT handler error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500

@app.route("/get", methods=["GET"])
def get_handler():
    try:
        key = request.args.get("key")
        if not key:
            return jsonify({"error": "missing key parameter"}), 400

        raw_value, meta = get_value(key)
        if raw_value is None:
            return jsonify({"found": False, "value": None}), 200

        value = decode_value(raw_value)
        return jsonify({"found": True, "value": value}), 200
    except Exception as e:
        logger.exception("GET handler error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500

@app.route("/all", methods=["GET"])
def all_handler():
    prefix = request.args.get("prefix", "")
    pref_bytes = prefix.encode("utf-8") if prefix else None

    def _list(client, p):
        items = []
        # client.get_prefix accepts bytes or str depending on version
        iterator = client.get_prefix(p) if p else client.get_all()
        for value, meta in iterator:
            try:
                k = getattr(meta, "key", None)
                if isinstance(k, (bytes, bytearray)):
                    k = k.decode("utf-8", errors="replace")
            except Exception:
                k = None
            v = decode_value(value)
            items.append({"key": k, "value": v})
        return items

    try:
        items = safe_etcd_call(_list, pref_bytes)
    except Exception as e:
        logger.exception("ALL handler error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "internal server error"}), 500

    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        rows = "".join(
            "<tr><td>{}</td><td>{}</td></tr>".format(
                html_escape.escape(i["key"] or ""), html_escape.escape(str(i["value"] or ""))
            )
            for i in items
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
    logger.info("Starting sidecar on %s:%d, connecting to etcd %s:%d", FLASK_HOST, FLASK_PORT, ETCD_HOST, ETCD_PORT)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)