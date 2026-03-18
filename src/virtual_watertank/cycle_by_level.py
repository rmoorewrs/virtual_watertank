#!/usr/bin/env python3
"""Send POST requests to the Flask level API, cycling level 0–100 with 2 s between updates."""

import time

import requests

API_URL = "http://127.0.0.1:5000/fill"
UPDATE_PERIOD_S = 1.5  # seconds between each POST
LEVEL_MAX = 100
LEVEL_MIN = 0
STEP_DELTA = 2  # level change per update (0, 1, 2, ... 100, 99, ... 0)


def main():
    level = float(LEVEL_MIN)
    direction = 1  # 1 = toward 100, -1 = toward 0

    print(f"POSTing level to {API_URL} every {UPDATE_PERIOD_S} s (0–100). Ctrl+C to stop.")
    while True:
        try:
            resp = requests.post(API_URL, json={"delta_level": int(round(level))}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"POST failed: {e}")

        level += direction * STEP_DELTA
        if level >= LEVEL_MAX:
            level = LEVEL_MAX
            direction = -1
        elif level <= LEVEL_MIN:
            level = LEVEL_MIN
            direction = 1

        time.sleep(UPDATE_PERIOD_S)


if __name__ == "__main__":
    main()
