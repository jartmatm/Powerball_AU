from __future__ import annotations

from typing import Callable
import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")

from powerball_model import TrainingConfig, run_walk_forward_training
from powerball_scraper import fetch_history

LOGGER = Callable[[str], None]


def run_prediction_pipeline(
    logger: LOGGER | None = None,
    training_config: TrainingConfig | None = None,
) -> dict[str, object]:
    messages: list[str] = []

    def emit(message: str) -> None:
        messages.append(message)
        if logger:
            logger(message)

    history_frame, source_details = fetch_history(logger=emit)
    emit(f"[SCRAPE] Fuente de datos activa: {source_details['source']}.")
    emit(f"[SCRAPE] Total de sorteos disponibles: {len(history_frame)}.")

    result = run_walk_forward_training(
        history_frame=history_frame,
        config=training_config or TrainingConfig(),
        logger=emit,
    )
    prediction = result["prediction"]
    emit(
        f"Proximo sugerido desde el ultimo sorteo: "
        f"{prediction['numbers']} | PB: {prediction['powerball']}"
    )

    return {
        "prediction": prediction,
        "summary": result["summary"],
        "evaluations": result["evaluations"],
        "data_source": source_details["source"],
        "draw_count": len(history_frame),
        "output": "\n".join(messages),
    }
