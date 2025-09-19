# app.py
import runpy
import os
import time
from flask import Flask, jsonify

app = Flask(__name__)

SCRIPT_FILENAME = os.environ.get("STARTUP_SCRIPT", "script.py")

# Estado de la ejecución
_state = {
    "running": False,
    "last_run": None,
    "error": None
}

@app.route("/")
def home():
    return jsonify({
        "message": "✅ La app está corriendo. Usa /run para ejecutar el script.",
        "state": _state
    })

@app.route("/run", methods=["POST", "GET"])
def run_script():
    if _state["running"]:
        return jsonify({"status": "ya en ejecución", "state": _state}), 200
    
    try:
        _state["running"] = True
        _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        _state["error"] = None

        print(f"🔄 Ejecutando {SCRIPT_FILENAME} bajo demanda...")
        runpy.run_path(SCRIPT_FILENAME, run_name="__main__")
        print("✅ Script finalizado.")
        _state["running"] = False
        return jsonify({"status": "finalizado", "state": _state}), 200
    except Exception as e:
        print("❌ Error en el script:", e)
        _state["error"] = repr(e)
        _state["running"] = False
        return jsonify({"status": "error", "error": repr(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

