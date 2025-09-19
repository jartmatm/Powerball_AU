# app.py
import os
import time
import runpy
import io
import contextlib
from flask import Flask, jsonify, Response

app = Flask(__name__)

# Nombre del archivo que contiene tu código (por defecto script.py)
SCRIPT_FILENAME = os.environ.get("STARTUP_SCRIPT", "script.py")

_state = {
    "running": False,
    "last_start": None,
    "last_end": None,
    "last_status": None  # "ok" / "error" / None
}

@app.route("/")
def home():
    return jsonify({
        "message": "La app está corriendo. Usa /run para ejecutar el script, /status para ver el estado.",
        "script": SCRIPT_FILENAME,
        "state": _state
    })

@app.route("/status")
def status():
    return jsonify(_state)

@app.route("/run", methods=["GET", "POST"])
def run_script():
    # Evita ejecuciones concurrentes
    if _state["running"]:
        return jsonify({"status": "busy", "message": "Ya hay una ejecución en curso."}), 409

    # Comprueba existencia del archivo
    if not os.path.exists(SCRIPT_FILENAME):
        return jsonify({"status": "error", "message": f"No existe el archivo {SCRIPT_FILENAME}"}), 404

    _state["running"] = True
    _state["last_start"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    _state["last_end"] = None
    _state["last_status"] = None

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        # Capturamos stdout y stderr del script
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            # Ejecuta el script tal cual (top-level code se ejecuta)
            runpy.run_path(SCRIPT_FILENAME, run_name="__main__")

        stdout_contents = buf_out.getvalue()
        stderr_contents = buf_err.getvalue()

        combined = ""
        if stdout_contents:
            combined += "=== STDOUT ===\n" + stdout_contents + "\n"
        if stderr_contents:
            combined += "=== STDERR ===\n" + stderr_contents + "\n"
        if combined.strip() == "":
            combined = "(No hubo salida por stdout ni stderr)"

        _state["last_status"] = "ok"
        _state["last_end"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        _state["running"] = False

        # Devolvemos la salida en HTML para que se vea bien en el navegador
        return Response(f"<pre>{combined}</pre>", mimetype="text/html")

    except Exception as e:
        # Capturamos excepción y la mostramos junto con cualquier salida parcial
        stderr_contents = buf_err.getvalue() + f"\n[Exception captured in app]: {repr(e)}\n"
        stdout_contents = buf_out.getvalue()
        combined = ""
        if stdout_contents:
            combined += "=== STDOUT (parcial) ===\n" + stdout_contents + "\n"
        combined += "=== ERROR ===\n" + stderr_contents + "\n"

        _state["last_status"] = "error"
        _state["last_end"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        _state["running"] = False

        return Response(f"<pre>{combined}</pre>", mimetype="text/html"), 500

if __name__ == "__main__":
    # Modo desarrollo: puerto por defecto 10000 (ajusta con PORT si lo necesitas)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


