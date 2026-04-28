from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Callable
import warnings

from bs4 import BeautifulSoup
import pandas as pd

from url_years import urls as DEFAULT_URLS

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")

import requests

LOGGER = Callable[[str], None]
HISTORY_CACHE_PATH = Path("data/powerball_history.csv")
MAIN_COLUMNS = [f"Numero{i}" for i in range(1, 8)]
LEGACY_COLUMNS = ["draw_number", "draw_date"] + MAIN_COLUMNS + ["Powerball"]
HISTORY_COLUMNS = (
    ["draw_number", "draw_date"]
    + MAIN_COLUMNS
    + ["Powerball", "main_count", "main_max", "powerball_max"]
)
SEVEN_NUMBER_FORMAT_START = pd.Timestamp("2018-04-19")
DRAW_BLOCK_PATTERN = re.compile(
    r"Draw\s+([\d,]+)\s+"
    r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})"
    r"(.*?)(?=Draw\s+[\d,]+|$)",
    re.DOTALL,
)


def _silent_logger(_message: str) -> None:
    return None


def _persist_cache(history_frame: pd.DataFrame, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    history_frame.to_csv(cache_path, index=False)


def _is_compatible_cache(history_frame: pd.DataFrame) -> bool:
    return all(column in history_frame.columns for column in HISTORY_COLUMNS)


def _migrate_legacy_cache(history_frame: pd.DataFrame) -> pd.DataFrame:
    if not all(column in history_frame.columns for column in LEGACY_COLUMNS):
        raise ValueError("El cache local no coincide con el esquema esperado.")

    migrated = history_frame.copy()
    migrated["draw_date"] = pd.to_datetime(migrated["draw_date"])
    six_number_mask = migrated["draw_date"] < SEVEN_NUMBER_FORMAT_START
    migrated["main_count"] = 7
    migrated["main_max"] = 35
    migrated["powerball_max"] = 20
    migrated.loc[six_number_mask, "main_count"] = 6
    migrated.loc[six_number_mask, "main_max"] = 40
    migrated.loc[six_number_mask, "Powerball"] = migrated.loc[six_number_mask, "Numero7"]
    migrated.loc[six_number_mask, "Numero7"] = 0
    return migrated[HISTORY_COLUMNS].sort_values(["draw_date", "draw_number"]).reset_index(drop=True)


def load_cached_history(cache_path: Path = HISTORY_CACHE_PATH) -> pd.DataFrame:
    if not cache_path.exists():
        raise FileNotFoundError(f"No existe cache local en {cache_path}")

    history_frame = pd.read_csv(cache_path, parse_dates=["draw_date"])
    if not _is_compatible_cache(history_frame):
        history_frame = _migrate_legacy_cache(history_frame)
        _persist_cache(history_frame, cache_path)

    return history_frame.sort_values(["draw_date", "draw_number"]).reset_index(drop=True)


def parse_archive_html(html: str) -> list[dict[str, object]]:
    text = "\n".join(BeautifulSoup(html, "html.parser").stripped_strings)
    draws: list[dict[str, object]] = []

    for match in DRAW_BLOCK_PATTERN.finditer(text):
        draw_number = int(match.group(1).replace(",", ""))
        draw_date = datetime.strptime(match.group(2), "%A %d %B %Y")
        values = [int(value) for value in re.findall(r"\b\d+\b", match.group(3))]
        if len(values) not in (6, 7, 8):
            continue

        main_numbers = values[:-1]
        powerball = values[-1]
        main_count = len(main_numbers)

        if main_count == 5:
            main_max = 45
            powerball_max = 45
        elif main_count == 6:
            main_max = 40
            powerball_max = 20
        else:
            main_max = 35
            powerball_max = 20

        if any(number < 1 or number > main_max for number in main_numbers):
            continue
        if powerball < 1 or powerball > powerball_max:
            continue

        padded_main_numbers = main_numbers + [0] * (len(MAIN_COLUMNS) - main_count)
        row = {
            "draw_number": draw_number,
            "draw_date": draw_date,
            "Powerball": powerball,
            "main_count": main_count,
            "main_max": main_max,
            "powerball_max": powerball_max,
        }
        for index, number in enumerate(padded_main_numbers, start=1):
            row[f"Numero{index}"] = number
        draws.append(row)

    return draws


def fetch_history(
    url_map: dict[int, str] | None = None,
    cache_path: Path = HISTORY_CACHE_PATH,
    logger: LOGGER | None = None,
    timeout: int = 20,
) -> tuple[pd.DataFrame, dict[str, object]]:
    url_map = url_map or DEFAULT_URLS
    logger = logger or _silent_logger
    records: list[dict[str, object]] = []
    failed_years: list[int] = []

    session = requests.Session()
    session.headers.update({"User-Agent": "PowerBall_AU/1.0"})

    for year, url in sorted(url_map.items(), reverse=True):
        logger(f"[SCRAPE] Consultando archivo {year}...")
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            year_records = parse_archive_html(response.text)
            logger(f"[SCRAPE] {year}: {len(year_records)} sorteos detectados.")
            records.extend(year_records)
        except requests.RequestException as exc:
            failed_years.append(year)
            logger(f"[SCRAPE] Error consultando {year}: {exc}")

    if records:
        history_frame = pd.DataFrame(records, columns=HISTORY_COLUMNS)
        history_frame = (
            history_frame.drop_duplicates(subset=["draw_number"])
            .sort_values(["draw_date", "draw_number"])
            .reset_index(drop=True)
        )

        if failed_years and cache_path.exists():
            try:
                cached_history = load_cached_history(cache_path)
            except ValueError:
                cached_history = None

            if cached_history is not None and len(cached_history) >= len(history_frame):
                logger("[SCRAPE] Hubo anos fallidos; usando cache local completo.")
                return cached_history, {"source": "cache", "failed_years": failed_years}

        _persist_cache(history_frame, cache_path)
        logger(f"[SCRAPE] Historial consolidado: {len(history_frame)} sorteos.")
        return history_frame, {"source": "remote", "failed_years": failed_years}

    if cache_path.exists():
        try:
            cached_history = load_cached_history(cache_path)
            logger("[SCRAPE] Sin respuesta remota; cargando cache local.")
            return cached_history, {"source": "cache", "failed_years": failed_years}
        except ValueError:
            logger("[SCRAPE] El cache local es antiguo y no se puede reutilizar.")

    raise RuntimeError(
        "No se pudo obtener el historial de sorteos desde la web y tampoco existe cache local."
    )
