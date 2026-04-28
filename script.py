import argparse
import sys

from powerball_service import run_prediction_pipeline


def build_parser():
    parser = argparse.ArgumentParser(
        description="Ejecuta la logica de prediccion PowerBall AU sin levantar la UI.",
        epilog=(
            "Ejemplos:\n"
            "  .venv/bin/python script.py --mode full\n"
            "  .venv/bin/python script.py --mode cache\n"
            "  .venv/bin/python script.py --mode since-2019\n"
            "  .venv/bin/python script.py --source cache --min-year 2019\n"
            "  .venv/bin/python script.py --source remote --min-year 2019"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=("default", "full", "cache", "since-2019"),
        default="default",
        help=(
            "Atajo listo para usar: 'full' hace web scraping completo, "
            "'cache' usa solo el CSV local y 'since-2019' scrapea desde 2019."
        ),
    )
    parser.add_argument(
        "--source",
        choices=("auto", "remote", "cache"),
        default="auto",
        help=(
            "Origen de datos: 'auto' intenta scraper y cae a cache, "
            "'remote' fuerza web scraping y 'cache' usa solo CSV local."
        ),
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Ano minimo para limitar el historial. Ejemplo: --min-year 2019",
    )
    return parser


def resolve_history_options(args):
    if args.mode == "full":
        return "remote", None
    if args.mode == "cache":
        return "cache", None
    if args.mode == "since-2019":
        return "remote", 2019
    return args.source, args.min_year


def main():
    args = build_parser().parse_args()
    history_source, min_year = resolve_history_options(args)
    try:
        result = run_prediction_pipeline(
            history_source=history_source,
            min_year=min_year,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(result["output"])


if __name__ == "__main__":
    main()
