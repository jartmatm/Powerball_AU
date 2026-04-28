from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import tensorflow as tf
from tensorflow.keras import layers, models, regularizers

LOGGER = Callable[[str], None]
MAIN_COLUMNS = [f"Numero{i}" for i in range(1, 8)]
META_COLUMNS = ["main_count", "main_max", "powerball_max"]
OUTPUT_COLUMNS = MAIN_COLUMNS + ["Powerball"]
INPUT_COLUMNS = OUTPUT_COLUMNS + META_COLUMNS
MAIN_SLOT_COUNT = 7
GLOBAL_NUMBER_MAX = 45.0


@dataclass(frozen=True)
class TrainingConfig:
    warmup_epochs: int = 24
    update_epochs: int = 2
    batch_size: int = 16
    replay_window: int = 48
    shuffle: bool = False
    learning_rate: float = 5e-4
    hidden_units: tuple[int, ...] = (48, 24, 12)
    hidden_activation: str = "elu"
    output_activation: str = "sigmoid"
    l2_strength: float = 1e-4
    random_seed: int = 42


def _silent_logger(_message: str) -> None:
    return None


def _history_to_input_matrix(history_frame: pd.DataFrame) -> np.ndarray:
    return history_frame[INPUT_COLUMNS].to_numpy(dtype=np.float32)


def _history_to_output_matrix(history_frame: pd.DataFrame) -> np.ndarray:
    return history_frame[OUTPUT_COLUMNS].to_numpy(dtype=np.float32)


def scale_input_matrix(draws: np.ndarray) -> np.ndarray:
    scaled = np.empty_like(draws, dtype=np.float32)
    scaled[:, : len(OUTPUT_COLUMNS)] = draws[:, : len(OUTPUT_COLUMNS)] / GLOBAL_NUMBER_MAX
    scaled[:, len(OUTPUT_COLUMNS)] = draws[:, len(OUTPUT_COLUMNS)] / MAIN_SLOT_COUNT
    scaled[:, len(OUTPUT_COLUMNS) + 1] = draws[:, len(OUTPUT_COLUMNS) + 1] / GLOBAL_NUMBER_MAX
    scaled[:, len(OUTPUT_COLUMNS) + 2] = draws[:, len(OUTPUT_COLUMNS) + 2] / GLOBAL_NUMBER_MAX
    return np.clip(scaled, 0.0, 1.0)


def scale_output_matrix(draws: np.ndarray) -> np.ndarray:
    return np.clip(draws / GLOBAL_NUMBER_MAX, 0.0, 1.0)


def inverse_scale_output(prediction: np.ndarray) -> np.ndarray:
    return np.clip(prediction, 0.0, 1.0) * GLOBAL_NUMBER_MAX


def build_model(config: TrainingConfig) -> tf.keras.Model:
    tf.keras.utils.set_random_seed(config.random_seed)
    model = models.Sequential([layers.Input(shape=(len(INPUT_COLUMNS),))])

    for units in config.hidden_units:
        model.add(
            layers.Dense(
                units,
                activation=config.hidden_activation,
                kernel_regularizer=regularizers.l2(config.l2_strength),
            )
        )

    model.add(layers.Dense(len(OUTPUT_COLUMNS), activation=config.output_activation))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss=tf.keras.losses.Huber(),
    )
    return model


def postprocess_prediction(
    vector: np.ndarray,
    main_count: int,
    main_max: int,
    powerball_max: int,
) -> dict[str, object]:
    rounded = np.rint(vector[: len(OUTPUT_COLUMNS)]).astype(int)
    unique_main_numbers: list[int] = []
    used_numbers: set[int] = set()

    for value in rounded[:MAIN_SLOT_COUNT]:
        if value <= 0:
            continue

        candidate = int(np.clip(value, 1, main_max))
        while candidate in used_numbers:
            candidate += 1
            if candidate > main_max:
                candidate = 1
        unique_main_numbers.append(candidate)
        used_numbers.add(candidate)
        if len(unique_main_numbers) == main_count:
            break

    filler = 1
    while len(unique_main_numbers) < main_count:
        if filler not in used_numbers:
            unique_main_numbers.append(filler)
            used_numbers.add(filler)
        filler += 1
        if filler > main_max:
            filler = 1

    unique_main_numbers.sort()
    powerball = int(np.clip(rounded[MAIN_SLOT_COUNT], 1, powerball_max))
    return {
        "numbers": unique_main_numbers,
        "powerball": powerball,
        "main_count": main_count,
        "main_max": main_max,
        "powerball_max": powerball_max,
    }


def _prediction_to_vector(prediction: dict[str, object]) -> np.ndarray:
    vector = np.zeros(len(OUTPUT_COLUMNS), dtype=np.float32)
    for index, value in enumerate(prediction["numbers"]):
        vector[index] = value
    vector[-1] = prediction["powerball"]
    return vector


def _predict_next_draw(
    model: tf.keras.Model,
    current_draw: np.ndarray,
    main_count: int,
    main_max: int,
    powerball_max: int,
) -> dict[str, object]:
    scaled_prediction = model(scale_input_matrix(current_draw), training=False).numpy()[0]
    return postprocess_prediction(
        inverse_scale_output(scaled_prediction),
        main_count=main_count,
        main_max=main_max,
        powerball_max=powerball_max,
    )


def _summarize_walk_forward(evaluations: list[dict[str, float]]) -> dict[str, float]:
    if not evaluations:
        return {
            "evaluated_steps": 0,
            "average_main_hits": 0.0,
            "powerball_hit_rate": 0.0,
            "average_absolute_error": 0.0,
        }

    return {
        "evaluated_steps": len(evaluations),
        "average_main_hits": float(np.mean([step["main_hits"] for step in evaluations])),
        "powerball_hit_rate": float(np.mean([step["powerball_hit"] for step in evaluations])),
        "average_absolute_error": float(np.mean([step["mae"] for step in evaluations])),
    }


def run_walk_forward_training(
    history_frame: pd.DataFrame,
    config: TrainingConfig | None = None,
    logger: LOGGER | None = None,
) -> dict[str, object]:
    config = config or TrainingConfig()
    logger = logger or _silent_logger
    input_matrix = _history_to_input_matrix(history_frame)
    output_matrix = _history_to_output_matrix(history_frame)

    if len(input_matrix) < 2:
        raise RuntimeError("Se necesitan al menos dos sorteos historicos para entrenar el modelo.")

    model = build_model(config)
    evaluations: list[dict[str, float]] = []
    logger(
        "[MODEL] Entrenamiento secuencial activado: "
        "cada sorteo aprende del anterior y luego predice el siguiente."
    )

    warmup_input = scale_input_matrix(input_matrix[:1])
    warmup_target = scale_output_matrix(output_matrix[1:2])
    for _ in range(config.warmup_epochs):
        model.train_on_batch(warmup_input, warmup_target)
    logger(
        f"[MODEL] Warm-up inicial con el par {int(history_frame.iloc[0]['draw_number'])}"
        f" -> {int(history_frame.iloc[1]['draw_number'])} durante {config.warmup_epochs} epochs."
    )

    for current_index in range(1, len(input_matrix) - 1):
        current_draw_number = int(history_frame.iloc[current_index]["draw_number"])
        next_draw_number = int(history_frame.iloc[current_index + 1]["draw_number"])
        next_main_count = int(history_frame.iloc[current_index + 1]["main_count"])
        next_main_max = int(history_frame.iloc[current_index + 1]["main_max"])
        next_powerball_max = int(history_frame.iloc[current_index + 1]["powerball_max"])
        prediction = _predict_next_draw(
            model,
            input_matrix[current_index : current_index + 1],
            main_count=next_main_count,
            main_max=next_main_max,
            powerball_max=next_powerball_max,
        )
        actual_next = output_matrix[current_index + 1]
        actual_main_numbers = {int(value) for value in actual_next[:MAIN_SLOT_COUNT] if int(value) > 0}
        predicted_vector = _prediction_to_vector(prediction)

        main_hits = len(set(prediction["numbers"]).intersection(actual_main_numbers))
        powerball_hit = int(prediction["powerball"] == int(actual_next[MAIN_SLOT_COUNT]))
        mae = float(np.mean(np.abs(predicted_vector - actual_next)))
        evaluations.append(
            {
                "main_hits": float(main_hits),
                "powerball_hit": float(powerball_hit),
                "mae": mae,
            }
        )

        if current_index <= 3 or current_index % 100 == 0 or current_index >= len(input_matrix) - 4:
            logger(
                f"[STEP {current_index}] Pronostico para sorteo {next_draw_number} "
                f"desde {current_draw_number}: {prediction['numbers']} | PB: {prediction['powerball']} "
                f"| aciertos principales: {main_hits}/{next_main_count} | PB: {powerball_hit}"
            )

        replay_start = max(0, current_index + 1 - config.replay_window)
        x_window = scale_input_matrix(input_matrix[replay_start : current_index + 1])
        y_window = scale_output_matrix(output_matrix[replay_start + 1 : current_index + 2])
        if len(x_window) > config.batch_size:
            x_window = x_window[-config.batch_size :]
            y_window = y_window[-config.batch_size :]

        for _ in range(config.update_epochs):
            model.train_on_batch(x_window, y_window)

    final_prediction = _predict_next_draw(
        model,
        input_matrix[-1:],
        main_count=int(history_frame.iloc[-1]["main_count"]),
        main_max=int(history_frame.iloc[-1]["main_max"]),
        powerball_max=int(history_frame.iloc[-1]["powerball_max"]),
    )
    summary = _summarize_walk_forward(evaluations)
    logger(f"[MODEL] Media de aciertos principales: {summary['average_main_hits']:.2f}")
    logger(f"[MODEL] Tasa de acierto Powerball: {summary['powerball_hit_rate']:.2%}")
    logger(f"[MODEL] Error absoluto medio: {summary['average_absolute_error']:.2f}")

    return {
        "prediction": final_prediction,
        "summary": summary,
        "evaluations": evaluations,
        "training_config": config,
    }
