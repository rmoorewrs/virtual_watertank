from __future__ import annotations
from nicegui import ui
import time
import requests
import threading
from threading import Thread
import random

# Tank States
# OVERFILL -- level is above the high limit
# LIMITHIGH -- exactly at high limit
# PPARTIAL -- between limits
# LIMITLOW -- exactly at low limit
# UNDERFILL -- level is below the low limit
#
# Level controller cycles between LIMITHIGH and LIMITLOW
# - OVERFILL and UNDERFILL are error states to be handled specially

# [TODO] add a file-based configuration for URLs and ports

LEVEL_ABS_MAX = 100
LEVEL_ABS_MIN = 0
WATERTANK_URL='watertank'
#WATERTANK_URL='localhost'
WATERTANK_PORT=5050
MY_PORT=5051

class TankCommunication:
    def __init__(self) -> None:
        self.ip_address = WATERTANK_URL
        self.ip_port = WATERTANK_PORT
        self.base_url = f"http://{self.ip_address}:{self.ip_port}"
        self.level_url = f"{self.base_url}/level"
        self.drain_url = f"{self.base_url}/drain"
        self.fill_url = f"{self.base_url}/fill"
        self.name = None
        self.uuid = None

    def get_current_level(self) -> int:
        # get the current level from the virtual tank
        current_level=0
        try:
            resp = requests.get(self.level_url,timeout=2)
            resp.raise_for_status()
            current_level=int(resp.json()['level'])
        except requests.RequestException as e:
            print(f"POST failed: {e}")
        return(current_level)

    def fill(self,increment: int) -> None:
        try:
            resp = requests.post(self.fill_url, json={'delta_level': increment}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"POST failed: {e}")

    def drain(self,increment: int) -> None:
        try:
            resp = requests.post(self.drain_url, json={'delta_level': increment}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"POST failed: {e}")

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
    id = hex(int(10000*random.random()))
    comm = None
    tank_states = ["OVERFILL","LIMITHIGH","PARTIAL","LIMITLOW","UNDERFILL"]
    tank_state = None
    dir_states = ["DRAIN","FILL"]
    dir_state = None
    run_states = ["CYCLE","HOLD"]
    run_state = "CYCLE"
    level_actual = 0
    level_setpoint = 50
    level_delta = 10 # setpoiint +/- delta
    level_increment = 1 # increment to fill or drain each cycle
    update_period = 1000

    def __init__(self,tank_comm:TankCommunication) -> None:
        self.comm=tank_comm
        self.level_actual = self.comm.get_current_level()
        self.initialize_controller()

    def print(self,msg: str):
        print(f"[id={self.id}]{msg}: level_actual={self.level_actual} tank_state={self.tank_state} dir_state={self.dir_state}")

    def limit_low(self)->int:
        low=self.level_setpoint - self.level_delta
        if low >= LEVEL_ABS_MIN:
            return low
        else:
            return LEVEL_ABS_MIN

    def limit_high(self)->int:
        high=self.level_setpoint + self.level_delta
        if high <= LEVEL_ABS_MAX:
            return high
        else:
            return LEVEL_ABS_MAX

    def running(self)->bool:
        if self.run_state == "CYCLE":
            return True
        else:
            return False

    def compute_current_state(self)->str:
        # update level
        self.level_actual = self.comm.get_current_level()
        if (self.level_actual < self.limit_low()):
            self.tank_state = "UNDERFILL"
        elif (self.level_actual == self.limit_low()):
            # always start to fill when we hit the low limit
            self.tank_state = "LIMITLOW"
        elif (self.level_actual == self.limit_high()):
            # always start to drain when we hit the high limit
            self.tank_state = "LIMITHIGH"
        elif (self.level_actual > self.limit_high()):
            self.tank_state = "OVERFILL"
        else:
            self.tank_state = "PARTIAL"
        return self.tank_state

    # handle the initial tank startup when we don't know the current state
    def initialize_controller(self):
        self.compute_current_state()
        self.print("INITIALIZING CONTROLLER:")


    def as_dict(self) -> dict[str, int | bool]:
        return {
            "run_state": self.run_state,
            "tank_state": self.tank_state,
            "level_actual": self.level_actual,
            "level_setpoint": self.level_setpoint,
            "level_delta": self.level_delta,
            "dir_state": self.dir_state,
            "update_period": self.update_period,
        }


class TankDraft:
    def __init__(self, *, level_setpoint: int, level_delta: int, update_period: int) -> None:
        self.level_setpoint = level_setpoint
        self.level_delta = level_delta
        self.update_period = update_period

# create objects
comm = TankCommunication()
state = TankState(tank_comm=comm)
draft = TankDraft(level_setpoint=state.level_setpoint, level_delta=state.level_delta,update_period=state.update_period)


def acheive_partial_state(state: TankState):
    if (state.tank_state== "OVERFILL"):
        while ( state.tank_state == "OVERFILL"):
            state.dir_state = "DRAIN"
            state.comm.drain(state.level_increment)
            state.print("acheive_partial_state() OVERFILL")
            time.sleep(float(state.update_period/1000.0))
            state.compute_current_state()
    elif (state.tank_state== "UNDERFILL"):
        while ( state.tank_state == "UNDERFILL"):
            state.dir_state = "FILL"
            state.comm.fill(state.level_increment)
            state.print("acheive_partial_state() UNDERFILL")
            time.sleep(float(state.update_period/1000.0))
            state.compute_current_state()
    else:
        return

# background task that controls the tank level
def cycle_task(state: TankState):
    # main loop
    while True: 
        incr=state.level_increment
        # compute the next state
        # NOTE: only the LIMITHIGH and LIMITLOW states should be able to change direction
        # OVERFILL and UNDERFILL take corrective action without affecting the dir_state variable
        state.compute_current_state()
        # OVERFILL or UNDERFILL
        if (state.tank_state== "OVERFILL" or state.tank_state == "UNDERFILL"):
            acheive_partial_state(state)
        # LIMITHIGH
        elif (state.tank_state== "LIMITHIGH"):
            # NOTE: CHANGING DIRECTION
            state.dir_state = "DRAIN"
            state.comm.drain(incr)
            state.print("cycle_task(): LIMITHIGH->DRAIN")
        # LIMITLOW
        elif (state.tank_state== "LIMITLOW"):
            # NOTE: CHANGING DIRECTION
            state.dir_state = "FILL"
            state.comm.fill(incr)
            state.print("cycle_task(): LIMITLOW->FILL")
        # PARTIAL
        elif (state.tank_state == "PARTIAL"):
            state.print("cycle_task() PARTIAL: ")
            if (state.dir_state == "DRAIN"):
                state.comm.drain(incr)
            else:
                state.comm.fill(incr)
        else:
            state.print("cycle_task(): error,illegal state ")
        
        # loop here until start button is clicked
        while state.run_state == "HOLD":
            time.sleep(0.2)

        # sleep
        time.sleep(float(state.update_period/1000.0))


# helper function
def bind_int(component, target_state, attr: str, *, min_value: int | None = None, max_value: int | None = None):
    component.bind_value(target_state, attr)

    def _coerce() -> None:
        try:
            value = int(getattr(target_state, attr))
        except (TypeError, ValueError):
            return

        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)

        setattr(target_state, attr, value)

    component.on_value_change(lambda _: _coerce())
    return component

# nicegui page
@ui.page("/")
def index() -> None:
    ui.markdown("## Virtual Watertank Level Controller")

    with ui.card().classes("w-full max-w-3xl"):
        run_btn = ui.button()

        def refresh_run_btn() -> None:
            run_btn.text = "CYCLE" if state.running() else "HOLD"
            run_btn.props(f"color={'positive' if state.running() else 'negative'}")

        def toggle_running() -> None:
            if (state.run_state == "CYCLE"):
                state.run_state = "HOLD"
            else:
                state.run_state = "CYCLE"
            refresh_run_btn()

        run_btn.on("click", lambda _: toggle_running())
        refresh_run_btn()

        bind_int(
            ui.number("Level setpoint", min=0, max=100, step=1).classes("w-60"),
            draft,
            "level_setpoint",
            min_value=0,
            max_value=100,
        )

        bind_int(
            ui.number("Level Delta (Range=Setpoint +/- Delta )", min=0, max=50, step=1).classes("w-60"),
            draft,
            "level_delta",
            min_value=0,
            max_value=50,
        )

        bind_int(
            ui.number("Update period (ms)", min=1, max=60_000, step=100).classes("w-60"),
            draft,
            "update_period",
            min_value=1,
            max_value=60_000,
        )

        def apply_draft_values() -> None:
            state.level_setpoint = draft.level_setpoint
            state.level_delta = draft.level_delta
            state.update_period = draft.update_period
            refresh_live()

        ui.button("Apply Changes", on_click=apply_draft_values).classes("w-24")

    ui.separator()
    ui.markdown("### Live object")
    live = ui.code("").classes("w-full max-w-3xl")

    def refresh_live() -> None:
        live.set_content("\n".join(f"{k}: {v}" for k, v in state.as_dict().items()))

    refresh_live()
    ui.timer(0.2, refresh_live)

def main():
    ui.run(title="Virtual Water Tank Level Controller", reload=False,port=MY_PORT)

if __name__ in {'__main__', '__mp_main__'}:
    run_cycle = Thread(target=cycle_task,daemon=True,args=(state,))
    run_cycle.start()
    main()
