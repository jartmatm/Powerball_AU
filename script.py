from powerball_service import run_prediction_pipeline


def main():
    result = run_prediction_pipeline()
    print(result["output"])


if __name__ == "__main__":
    main()
