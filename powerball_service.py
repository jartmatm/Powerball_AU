from __future__ import annotations

from typing import Callable
import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")

from powerball_model import TrainingConfig, run_walk_forward_training
from powerball_scraper import HistorySource, load_history

LOGGER = Callable[[str], None]


def _describe_scope(min_year: int | None) -> str:
    if min_year is None:
        return "historial completo disponible"
    return f"sorteos desde {min_year}"


def run_prediction_pipeline(
    logger: LOGGER | None = None,
    training_config: TrainingConfig | None = None,
    history_source: HistorySource = "auto",
    min_year: int | None = None,
) -> dict[str, object]:
    messages: list[str] = []

    def emit(message: str) -> None:
        messages.append(message)
        if logger:
            logger(message)

    history_frame, source_details = load_history(
        source=history_source,
        min_year=min_year,
        logger=emit,
    )
    emit(f"[SCRAPE] Fuente de datos activa: {source_details['source']}.")
    emit(f"[SCRAPE] Alcance solicitado: {_describe_scope(min_year)}.")
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
        "cache_path": source_details.get("cache_path"),
        "output": "\n".join(messages),
    }
