from datetime import date


START_YEAR = 1996
CURRENT_YEAR = date.today().year

urls = {}
for year in range(CURRENT_YEAR, START_YEAR - 1, -1):
    urls[year] = f"https://au.lottonumbers.com/powerball/results/{year}-archive"
