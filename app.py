# app.py
import threading
import runpy
import os
import time
from flask import Flask, jsonify

app = Flask(__name__)

# Nombre del archivo donde pegaste el código que me diste (no lo cambies)
SCRIPT_FILENAME = os.environ.get("STARTUP_SCRIPT", "script.py")

# Indicador de estado accesible vía HTTP
_state = {
    "started": False,
    "finished": False,
    "error": None,
    "start_time": None,
    "end_time": None
}

def run_startup_script():
    """
    Ejecuta el script completo tal como está guardado en SCRIPT_FILENAME.
    Usamos runpy.run_path para ejecutar el archivo como un script independiente
    (no como módulo importado), así no es necesario modificar el contenido.
    """
    try:
        _state["started"] = True
        _state["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"🔄 Ejecutando el script de inicio: {SCRIPT_FILENAME} (esto puede demorarse)...")
        # Ejecuta el script en el contexto propio (equivalente a ejecutar `python script.py`)
        runpy.run_path(SCRIPT_FILENAME, run_name="__main__")
        _state["finished"] = True
        _state["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("✅ Script finalizado.")
    except Exception as e:
        _state["error"] = repr(e)
        _state["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("❌ Error al ejecutar el script:", e)

# Arranca el script en un hilo separado para que el servidor web responda (y no quede bloqueado)
def start_background_runner():
    t = threading.Thread(target=run_startup_script, daemon=True)
    t.start()
    return t

# Iniciar el hilo una vez (al importar app.py)
_runner_thread = start_background_runner()

@app.route("/")
def root():
    """
    Endpoint simple que devuelve el estado del proceso de inicio.
    """
    return jsonify({
        "message": "La app está corriendo. El script proporcionado se está ejecutando en background.",
        "state": _state
    })

@app.route("/status")
def status():
    return jsonify(_state)

if __name__ == "__main__":
    # Modo desarrollo: arranca Flask (no usar en producción si usas gunicorn en Render)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
