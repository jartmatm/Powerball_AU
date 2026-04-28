import os
import time
import traceback

from flask import Flask, jsonify, render_template

app = Flask(__name__)

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


def _mark_run_finished(status):
    _state["running"] = False
    _state["last_status"] = status
    _state["last_end"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _execute_prediction():
    from powerball_service import run_prediction_pipeline

    _state["running"] = True
    _state["last_start"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    _state["last_end"] = None
    _state["last_status"] = None

    try:
        result = run_prediction_pipeline()
        _mark_run_finished("ok")
        return {
            "status": "ok",
            "output": result["output"],
            "prediction": result["prediction"],
            "summary": result["summary"],
            "draw_count": result["draw_count"],
            "data_source": result["data_source"],
            "state": _state_snapshot(),
        }, 200
    except Exception as exc:
        _mark_run_finished("error")
        return {
            "status": "error",
            "message": "La ejecucion del modelo fallo.",
            "output": "=== ERROR ===\n" + traceback.format_exc().rstrip(),
            "prediction": None,
            "error_type": type(exc).__name__,
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


@app.route("/api/predict", methods=["POST"])
@app.route("/run", methods=["POST"])
def run_prediction():
    if _state["running"]:
        return jsonify(
            {
                "status": "busy",
                "message": "Ya hay una ejecucion en curso.",
                "state": _state_snapshot(),
            }
        ), 409

    payload, status_code = _execute_prediction()
    return jsonify(payload), status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
