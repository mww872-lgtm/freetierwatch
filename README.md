# Free Tier Watch

Independent weekly tracker of what the **free plans** of popular AI chat services actually include.

- Every fact links to the official source and shows a "last checked" date.
- If something is not officially stated, we say so instead of guessing.
- No ads, no sponsors.

## How it works (technical)

1. `collector/collect.py` saves each service's official free-plan page as plain text (weekly, GitHub Actions).
2. `collector/diff.py` compares with the previous week.
3. `reader/read.py` turns changed pages into a structured table with an LLM; every item must carry a verbatim quote from the page, and quotes that are not found on the page are flagged for human review.
4. Results land in `data/plans.json`.

## Data and licenses

- Code: MIT (`LICENSE`). Our summaries and compiled data: CC BY 4.0, please credit Free Tier Watch (`CONTENT-LICENSE.md`).
- This repository holds the code and the site settings. The weekly data (raw page snapshots, every past check, extracted plans) lives in a separate private repository. The workflows check it out and point the scripts to it with `FTW_DATA_DIR`; without that variable the scripts use a local, git-ignored `data/` folder.
- What the site shows today is public on the site itself (`data.json`).

Status: early prototype.
