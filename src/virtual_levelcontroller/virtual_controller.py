from __future__ import annotations
from nicegui import ui
import time
import requests
import threading
from threading import Thread

LEVEL_ABS_MAX = 100
LEVEL_ABS_MIN = 0
WATERTANK_URL='watertank'
WATERTANK_PORT=5050
MY_PORT=5051

class TankConfig:
    def __init__(self) -> None:
        self.ip_address = WATERTANK_URL
        self.ip_port = WATERTANK_PORT
        self.base_url = f"http://{self.ip_address}:{self.ip_port}"
        self.level_url = f"{self.base_url}/level"
        self.drain_url = f"{self.base_url}/drain"
        self.fill_url = f"{self.base_url}/fill"
        self.name = None
        self.uuid = None

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "ip_address": self.ip_address,
            "ip_port": self.ip_port,
            "base_url": self.base_url,
            "level_url": self.level_url,
            "drain_url":self.drain_url,
            "fill_url": self.fill_url,
            "name": self.name,
            "uuid": self.uuid
        }

class TankState:
    def __init__(self,tconfig:TankConfig) -> None:
        self.running = True
        self.level_actual = LEVEL_ABS_MIN
        self.level_setpoint = 50
        self.level_range = 20
        self.level_min = LEVEL_ABS_MIN
        self.level_max = LEVEL_ABS_MAX
        self.level_delta = 1
        self.mode = 'drain'
        self.update_period = 1000
        self.tconfig = tconfig
        # set level min and max based on setpoint and range
        self.set_level_range()

    def is_full(self) -> bool:
        if (self.level_actual >= self.level_max):
            return True
        else:
            return False
    
    def is_empty(self) -> bool:
        if (self.level_actual <= self.level_min):
            return True
        else:
            return False
        
    def fill(self) -> None:
        self.level_actual += self.level_delta

    def drain(self) -> None:
        self.level_actual -= self.level_delta

    def set_level_range(self):
        max = self.level_setpoint+int(self.level_range/2)
        if max in range(LEVEL_ABS_MIN,LEVEL_ABS_MAX):
            self.level_max = max
        else:
            self.level_max = LEVEL_ABS_MAX
        min = self.level_setpoint-int(self.level_range/2)
        if max in range(LEVEL_ABS_MIN,LEVEL_ABS_MAX):
            self.level_min = min
        else:
            self.level_min = LEVEL_ABS_MIN

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "running": self.running,
            "level_setpoint": self.level_setpoint,
            "level_range": self.level_range,
            "level_min": self.level_min,
            "level_max": self.level_max,
            "mode": self.mode,
            "update_period": self.update_period,
        }


config = TankConfig()
state = TankState(config)


def cycle_task(state: TankState):
    # get the current tank level and figure out if we should be filling or draining
    state.running=True
    try:
        resp = requests.get(state.tconfig.level_url,timeout=2)
        resp.raise_for_status()
        state.level_actual=resp.json()['level']
    except requests.RequestException as e:
        print(f"POST failed: {e}")

    if (state.level_actual < state.level_max):
        print(f"Initial level={state.level_actual}, below upper limit={state.level_max}, Starting in fill mode")
        state.mode = 'fill'
    else:
        print(f"Initial level={state.level_actual}, above upper limit={state.level_max}, Starting in drain mode")  
        state.mode = 'drain'

    # main loop
    while True: 
        # make sure the level range hasn't been changed.. should be done in UI [TODO]
        state.set_level_range()
        if (state.mode == 'fill'):
            # fill the tank by state.level_delta
            try:
                resp = requests.post(state.tconfig.fill_url, json={'delta_level': state.level_delta}, timeout=2)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"POST failed: {e}")
            # increment tank level and check whether it's time to switch to drain
            state.fill()
            if state.is_full():
                # time to switch directions
                print("cycle_task(): changing mode to drain")
                state.mode = 'drain'
        else: 
            # drain the tank by state.level_delta
            try:
                resp = requests.post(state.tconfig.drain_url, json={'delta_level': state.level_delta}, timeout=2)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"POST failed: {e}")
            # decrement tank level and check whether it's time to switch to fill
            state.drain()
            if state.is_empty():
                # time to switch directions
                print("cycle_task(): changing mode to fill")
                state.mode = 'fill'   
        
        if state.running is False:
            while state.running is False:
                time.sleep(float(state.update_period/1000.0))


        # sleep
        print(f"cycle_task(): sleeping for {state.update_period} ms, level={state.level_actual}")
        time.sleep(float(state.update_period/1000.0))

# helper function to make sure values are valid
def bind_int(component, attr: str, *, min_value: int | None = None, max_value: int | None = None):
    component.bind_value(state, attr)

    def _coerce() -> None:
        try:
            value = int(getattr(state, attr))
        except (TypeError, ValueError):
            return

        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)

        setattr(state, attr, value)

    component.on_value_change(lambda _: _coerce())
    return component


@ui.page("/")
def index() -> None:
    ui.markdown("## Virtual Watertank Level Controller")

    with ui.card().classes("w-full max-w-3xl"):
        run_btn = ui.button()

        def refresh_run_btn() -> None:
            run_btn.text = "Running: ON" if state.running else "Running: OFF"
            run_btn.props(f"color={'positive' if state.running else 'negative'}")

        def toggle_running() -> None:
            state.running = not state.running
            refresh_run_btn()

        run_btn.on("click", lambda _: toggle_running())
        refresh_run_btn()

        bind_int(
            ui.number("Level setpoint", min=0, max=100, step=1).classes("w-60"),
            "level_setpoint",
            min_value=0,
            max_value=100,
        )

        bind_int(
            ui.number("Level range", min=0, max=100, step=1).classes("w-60"),
            "level_range",
            min_value=0,
            max_value=50,
        )

        bind_int(
            ui.number("Update period (ms)", min=100, max=60000, step=50).classes("w-60"),
            "update_period",
            min_value=50,
            max_value=60000,
        )

    ui.separator()
    ui.markdown("### Live object")
    live = ui.code("").classes("w-full max-w-3xl")

    def refresh_live() -> None:
        live.set_content("\n".join(f"{k}: {v}" for k, v in state.as_dict().items()))

    refresh_live()
    ui.timer(0.2, refresh_live)

def main():
    ui.run(title="Virtual Water Tank Level Controller", reload=True,port=MY_PORT)

if __name__ in {'__main__', '__mp_main__'}:
    run_cycle = Thread(target=cycle_task,daemon=True,args=(state,))
    run_cycle.start()
    main()
