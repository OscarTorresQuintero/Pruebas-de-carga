from flask import Flask, jsonify, request
import hashlib

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/procesar", methods=["POST"])
def procesar():
    datos = request.get_json(silent=True) or {}
    texto = str(datos.get("texto", "pedido"))
    resultado = texto.encode()
    for _ in range(50000):
        resultado = hashlib.sha256(resultado).digest()
    return jsonify(estado="procesado", hash=resultado.hex()[:16])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)