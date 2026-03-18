#!/usr/bin/env python3
"""Send POST requests to the Flask level API, cycling level 0–100 with time between updates."""
import time
import requests
import threading
from threading import Thread

API_URL = "http://127.0.0.1:5000/"
UPDATE_PERIOD_S = 1 # seconds between each POST
LEVEL_MAX = 75
LEVEL_MIN = 25
DELTA = 1
MODE = 'fill' # can be either 'fill' or 'drain'


def validate_range(value,min,max):
    """Validator for min-max range."""
    num = int(value)
    if num <= min:
        num = min
    elif num >= max:
        num = max
    return num

def cycle_task(should_stop:threading.Event):
    # get the current tank level and figure out if we should be filling or draining
    try:
        resp = requests.get(API_URL+'level',timeout=2)
        resp.raise_for_status()
        level=resp.json()['level']
    except requests.RequestException as e:
        print(f"POST failed: {e}")

    if (level < LEVEL_MAX):
        print(f"Initial level={level}, Starting in fill mode")
        MODE = 'fill'
    else:
        print(f"Initial level={level}, Starting in drain mode")  
        MODE = 'drain'


    while not should_stop.is_set():
        try:
            resp = requests.post(API_URL+MODE, json={'delta_level': DELTA}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"POST failed: {e}")
        
        if (MODE == 'fill'):
            level = validate_range(level+DELTA,LEVEL_MIN,LEVEL_MAX)
            if (level >= LEVEL_MAX):
                # time to switch directions
                MODE = 'drain'
        else:
            level = validate_range(level-DELTA,LEVEL_MIN,LEVEL_MAX)
            if (level <= LEVEL_MIN):
                # time to switch directions
                MODE = 'fill'   
        
        # sleep
        time.sleep(UPDATE_PERIOD_S)


def main():
    print(f"Sending command to {API_URL} every {UPDATE_PERIOD_S} s ({LEVEL_MIN}–{LEVEL_MAX})")
    print(f"fill URL = {API_URL}fill, drain URL = {API_URL}drain")
    print("Running level control task.")

    should_stop = threading.Event() # create empty event to tell the task when to quit
    run_cycle = Thread(target=cycle_task,daemon=True,args=(should_stop,))
    run_cycle.start()
    print("task started")
    time.sleep(1)

    input("hit any key to exit ...")
    should_stop.set()
    print("Done")

if __name__ == "__main__":
    main()
