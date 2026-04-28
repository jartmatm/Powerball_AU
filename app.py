import contextlib
import io
import os
import re
import runpy
import time

from flask import Flask, jsonify, render_template

app = Flask(__name__)

SCRIPT_FILENAME = os.environ.get("STARTUP_SCRIPT", "script.py")
PREDICTION_PATTERN = re.compile(
    r"Proximo sugerido desde el ultimo sorteo:\s*\[(.*?)\]\s*\|\s*PB:\s*(\d+)"
)

_state = {
    "running": False,
    "last_start": None,
    "last_end": None,
    "last_status": None,
}

FEATURE_CARDS = [
    {"title": "Numbers Generator", "icon": "cards"},
    {"title": "Quick Pick", "icon": "chips"},
    {"title": "Lucky Stats", "icon": "dice"},
    {"title": "Gambling Tools", "icon": "slot"},
    {"title": "Casino Zone", "icon": "roulette"},
]

FOOTER_FEATURES = [
    {"title": "Secure", "description": "256-bit encryption", "icon": "shield"},
    {"title": "Data Driven", "description": "AI powered algorithms", "icon": "chart"},
    {"title": "Accuracy", "description": "Maximize your odds", "icon": "target"},
]

STATUS_METRICS = [
    {"label": "CONNECTED", "value": "ONLINE", "level": 96},
    {"label": "ENCRYPTION", "value": "ACTIVE", "level": 88},
    {"label": "SIGNAL", "value": "STRONG", "level": 74},
]


def _state_snapshot():
    return dict(_state)


def _extract_prediction(text):
    normalized = (
        text.replace("Próximo", "Proximo")
        .replace("último", "ultimo")
        .replace("sugerido", "sugerido")
    )
    match = PREDICTION_PATTERN.search(normalized)
    if not match:
        return None

    raw_numbers = [chunk.strip() for chunk in match.group(1).split(",") if chunk.strip()]
    try:
        numbers = [int(chunk) for chunk in raw_numbers]
        powerball = int(match.group(2))
    except ValueError:
        return None

    if len(numbers) != 7:
        return None

    return {"numbers": numbers, "powerball": powerball}


def _build_output(stdout_contents, stderr_contents):
    blocks = []
    if stdout_contents:
        blocks.append("=== STDOUT ===\n" + stdout_contents.rstrip())
    if stderr_contents:
        blocks.append("=== STDERR ===\n" + stderr_contents.rstrip())
    return "\n\n".join(blocks) if blocks else "(No hubo salida por stdout ni stderr)"


def _mark_run_finished(status):
    _state["running"] = False
    _state["last_status"] = status
    _state["last_end"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _execute_script():
    _state["running"] = True
    _state["last_start"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    _state["last_end"] = None
    _state["last_status"] = None

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            runpy.run_path(SCRIPT_FILENAME, run_name="__main__")

        stdout_contents = buf_out.getvalue()
        stderr_contents = buf_err.getvalue()
        combined = _build_output(stdout_contents, stderr_contents)
        prediction = _extract_prediction(stdout_contents)

        _mark_run_finished("ok")
        return {
            "status": "ok",
            "output": combined,
            "prediction": prediction,
            "state": _state_snapshot(),
        }, 200
    except Exception as exc:
        stdout_contents = buf_out.getvalue()
        stderr_contents = buf_err.getvalue()
        if stderr_contents:
            stderr_contents = stderr_contents.rstrip() + "\n"
        stderr_contents += f"[Exception captured in app]: {exc!r}\n"
        combined = _build_output(stdout_contents, stderr_contents)

        _mark_run_finished("error")
        return {
            "status": "error",
            "message": "La ejecucion del modelo fallo.",
            "output": combined,
            "prediction": None,
            "state": _state_snapshot(),
        }, 500


@app.route("/")
def home():
    return render_template(
        "index.html",
        feature_cards=FEATURE_CARDS,
        footer_features=FOOTER_FEATURES,
        status_metrics=STATUS_METRICS,
        placeholder_numbers=["--"] * 7,
        matrix_columns=list(range(16)),
        jackpot_amount="$150,000,000",
        next_draw_day="THURSDAY",
        next_draw_time="7:30 PM AEST",
        state=_state_snapshot(),
    )


@app.route("/status")
def status():
    return jsonify(_state_snapshot())


@app.route("/run", methods=["GET", "POST"])
def run_script():
    if _state["running"]:
        return jsonify(
            {
                "status": "busy",
                "message": "Ya hay una ejecucion en curso.",
                "state": _state_snapshot(),
            }
        ), 409

    if not os.path.exists(SCRIPT_FILENAME):
        return jsonify(
            {
                "status": "error",
                "message": f"No existe el archivo {SCRIPT_FILENAME}",
                "state": _state_snapshot(),
            }
        ), 404

    payload, status_code = _execute_script()
    return jsonify(payload), status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
