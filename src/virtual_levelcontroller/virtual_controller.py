from __future__ import annotations
from nicegui import ui
import argparse
import time
import requests
import threading
from threading import Thread
import random
import json
from pathlib import Path
import yaml
import uuid

# Tank States
# OVERFILL -- level is above the high limit
# LIMITHIGH -- exactly at high limit
# PPARTIAL -- between limits
# LIMITLOW -- exactly at low limit
# UNDERFILL -- level is below the low limit
#
# Level controller cycles between LIMITHIGH and LIMITLOW
# - OVERFILL and UNDERFILL are error states to be handled specially

# example config.yaml
"""
watertank:
    tank_ip_address: '127.0.0.1'
    tank_ip_port: '5050'
controller:
    controller_ip_address: '127.0.0.1'
    controller_ip_port: '5051'
"""

# some global defaults
LEVEL_ABS_MAX = 100
LEVEL_ABS_MIN = 0
CONFIG_FILENAME = 'config.yaml'
WATERTANK_URL='watertank'
WATERTANK_PORT=5050
CONTROLLER_URL = 'levelcontroller'
CONTROLLER_PORT=5051
DEFAULT_TANK_NAME='tank'
DEFAULT_CONTROLLER_NAME='controller'

class LevelController:
    config_file = None
    tank_ip_address = None
    tank_ip_port = None
    controller_ip_address = None
    controller_ip_port = None
    base_url = None
    level_url = None
    drain_url = None
    fill_url = None
    name = None
    uuid = None

    def __init__(self, config_file: str | None = CONFIG_FILENAME) -> None:
        if config_file is not None:
            config_path = Path(config_file)
            try:
                with config_path.open('r', encoding='utf-8') as file:
                    config_data = yaml.safe_load(file) or {}
            except FileNotFoundError:
                print(f'Config file not found: {config_path}. Using built-in defaults.')
                config_data = {}

            # Supports either top-level keys or nested sections.
            self.tank_config = config_data.get('watertank', config_data)
            self.controller_config = config_data.get('levelcontroller', config_data)
            self.tank_ip_address = self.tank_config.get('tank_ip_address',WATERTANK_URL)
            self.tank_ip_port = self.tank_config.get('tank_ip_port',WATERTANK_PORT)
            self.controller_ip_address = self.controller_config.get('controller_ip_address', CONTROLLER_URL)
            self.controller_ip_port = self.controller_config.get('controller_ip_port', CONTROLLER_PORT)
        else:
            self.tank_ip_address = WATERTANK_URL
            self.tank_ip_port = int(WATERTANK_PORT)
            self.controller_ip_address = CONTROLLER_URL
            self.controller_ip_port = int(CONTROLLER_PORT)


        # create sub URLS based on main tank ip address    
        self.base_url = f'http://{self.tank_ip_address}:{self.tank_ip_port}'
        self.level_url = f'{self.base_url}/level'
        self.drain_url = f'{self.base_url}/drain'
        self.fill_url = f'{self.base_url}/fill'
        self.name = self.controller_config.get('name',DEFAULT_CONTROLLER_NAME)
        self.uuid = self.controller_config.get('uuid',uuid.uuid4())
        self.name = f'{self.name}-{str(self.uuid)[-4:]}'



    def get_tank_level(self) -> int:
        # get the current level from the virtual tank
        current_level=0
        try:
            resp = requests.get(self.level_url,timeout=2)
            resp.raise_for_status()
            current_level=int(resp.json()['level'])
        except requests.RequestException as e:
            print(f'POST failed: {e}')
        return(current_level)

    def fill(self,increment: int) -> None:
        try:
            resp = requests.post(self.fill_url, json={'delta_level': increment}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f'POST failed: {e}')

    def drain(self,increment: int) -> None:
        try:
            resp = requests.post(self.drain_url, json={'delta_level': increment}, timeout=2)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f'POST failed: {e}')

    def as_dict(self) -> dict[str, int | bool]:
        return {
            'tank_ip_address': self.tank_ip_address,
            'tank_ip_port': self.tank_ip_port,
            'controller_ip_address': self.controller_ip_address,
            'controller_ip_port': self.controller_ip_port,
            'base_url': self.base_url,
            'level_url': self.level_url,
            'drain_url':self.drain_url,
            'fill_url': self.fill_url,
            'name': self.name,
            'uuid': self.uuid
        }

    def as_config(self, format: str = 'json') -> str:
        config = {
            'watertank': {
                'tank_ip_address': self.tank_ip_address,
                'tank_ip_port': self.tank_ip_port,
            },
            'controller':{
                'controller_ip_address': self.controller_ip_address,
                'controller_ip_port': self.controller_ip_port,
            }
        }

        output_format = format.lower()
        if output_format == 'json':
            return json.dumps(config, indent=2)
        if output_format == 'yaml':
            try:
                import yaml  # type: ignore
            except ImportError as e:
                raise ImportError('PyYAML is required to serialize YAML configuration.') from e
            return yaml.safe_dump(config, sort_keys=False)
        raise ValueError('format must be either "json" or "yaml" ')


class TankState:
    id = None
    controller = None
    tank_states = ['OVERFILL','LIMITHIGH','PARTIAL','LIMITLOW','UNDERFILL']
    tank_state = None
    dir_states = ['DRAIN','FILL']
    dir_state = None
    run_states = ['CYCLE','HOLD']
    run_state = 'CYCLE'
    level_actual = 0
    level_setpoint = 50
    level_delta = 10 # setpoiint +/- delta
    level_increment = 1 # increment to fill or drain each cycle
    update_period = 1000
    name = DEFAULT_TANK_NAME

    def __init__(self,level_controller:LevelController) -> None:
        self.controller=level_controller
        self.level_actual = self.controller.get_tank_level()
        self.level_setpoint = int(self.controller.controller_config.get("level_setpoint",50))
        self.level_delta = int(self.controller.controller_config.get("level_delta",10))
        self.id = str(self.controller.uuid)[-6:]
        self.name = self.controller.name
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
        if self.run_state == 'CYCLE':
            return True
        else:
            return False

    def compute_current_state(self)->str:
        # update level
        self.level_actual = self.controller.get_tank_level()
        if (self.level_actual < self.limit_low()):
            self.tank_state = 'UNDERFILL'
        elif (self.level_actual == self.limit_low()):
            # always start to fill when we hit the low limit
            self.tank_state = 'LIMITLOW'
        elif (self.level_actual == self.limit_high()):
            # always start to drain when we hit the high limit
            self.tank_state = 'LIMITHIGH'
        elif (self.level_actual > self.limit_high()):
            self.tank_state = 'OVERFILL'
        else:
            self.tank_state = 'PARTIAL'
        return self.tank_state

    # handle the initial tank startup when we don't know the current state
    def initialize_controller(self):
        self.compute_current_state()
        self.print('INITIALIZING CONTROLLER:')


    def as_dict(self) -> dict[str, int | bool]:
        return {
            'run_state': self.run_state,
            'tank_state': self.tank_state,
            'level_actual': self.level_actual,
            'level_setpoint': self.level_setpoint,
            'level_delta': self.level_delta,
            'dir_state': self.dir_state,
            'update_period': self.update_period,
            'name': self.name,
            'uuid': self.controller.uuid,
        }


class TankDraft:
    def __init__(self, *, level_setpoint: int, level_delta: int, update_period: int) -> None:
        self.level_setpoint = level_setpoint
        self.level_delta = level_delta
        self.update_period = update_period

def parse_startup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Virtual Level Controller')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to YAML config file (default: config.yaml)',
    )
    args, _unknown = parser.parse_known_args()
    return args


# create objects
startup_args = parse_startup_args()
controller = LevelController(startup_args.config)
tank = TankState(level_controller=controller)
draft = TankDraft(level_setpoint=tank.level_setpoint, level_delta=tank.level_delta,update_period=tank.update_period)


def achieve_partial_state(state: TankState):
    if (tank.tank_state== 'OVERFILL'):
        while ( tank.tank_state == 'OVERFILL'):
            tank.dir_state = 'DRAIN'
            tank.controller.drain(tank.level_increment)
            tank.print('achieve_partial_state() OVERFILL')
            time.sleep(float(tank.update_period/1000.0))
            tank.compute_current_state()
    elif (tank.tank_state== 'UNDERFILL'):
        while ( tank.tank_state == 'UNDERFILL'):
            tank.dir_state = 'FILL'
            tank.controller.fill(tank.level_increment)
            tank.print('achieve_partial_state() UNDERFILL')
            time.sleep(float(tank.update_period/1000.0))
            tank.compute_current_state()
    else:
        return

# background task that controls the tank level
def cycle_task(state: TankState):
    # main loop
    while True: 
        incr=tank.level_increment
        # compute the next state
        # NOTE: only the LIMITHIGH and LIMITLOW states should be able to change direction
        # OVERFILL and UNDERFILL take corrective action without affecting the dir_state variable
        tank.compute_current_state()
        # OVERFILL or UNDERFILL
        if (tank.tank_state== 'OVERFILL' or tank.tank_state == 'UNDERFILL'):
            achieve_partial_state(state)
        # LIMITHIGH
        elif (tank.tank_state== 'LIMITHIGH'):
            # NOTE: CHANGING DIRECTION
            tank.dir_state = 'DRAIN'
            tank.controller.drain(incr)
            tank.print('cycle_task(): LIMITHIGH->DRAIN')
        # LIMITLOW
        elif (tank.tank_state== 'LIMITLOW'):
            # NOTE: CHANGING DIRECTION
            tank.dir_state = 'FILL'
            tank.controller.fill(incr)
            tank.print('cycle_task(): LIMITLOW->FILL')
        # PARTIAL
        elif (tank.tank_state == 'PARTIAL'):
            tank.print('cycle_task() PARTIAL: ')
            if (tank.dir_state == 'DRAIN'):
                tank.controller.drain(incr)
            else:
                tank.controller.fill(incr)
        else:
            tank.print('cycle_task(): error,illegal state ')
        
        # loop here until start button is clicked
        while tank.run_state == 'HOLD':
            time.sleep(0.2)

        # sleep
        time.sleep(float(tank.update_period/1000.0))


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
@ui.page('/')
def index() -> None:
    ui.markdown('## Virtual Level Controller')

    with ui.card().classes('w-full max-w-3xl'):
        run_btn = ui.button()

        def refresh_run_btn() -> None:
            run_btn.text = 'CYCLE' if tank.running() else 'HOLD'
            run_btn.props(f'color={"positive" if tank.running() else "negative"}')

        def toggle_running() -> None:
            if (tank.run_state == 'CYCLE'):
                tank.run_state = 'HOLD'
            else:
                tank.run_state = 'CYCLE'
            refresh_run_btn()

        run_btn.on('click', lambda _: toggle_running())
        refresh_run_btn()

        bind_int(
            ui.number('Level setpoint', min=0, max=100, step=1).classes('w-60'),
            draft,
            'level_setpoint',
            min_value=0,
            max_value=100,
        )

        bind_int(
            ui.number('Level Delta (Range=Setpoint +/- Delta )', min=0, max=50, step=1).classes('w-60'),
            draft,
            'level_delta',
            min_value=0,
            max_value=50,
        )

        bind_int(
            ui.number('Update period (ms)', min=1, max=60_000, step=100).classes('w-60'),
            draft,
            'update_period',
            min_value=1,
            max_value=60_000,
        )

        def apply_draft_values() -> None:
            tank.level_setpoint = draft.level_setpoint
            tank.level_delta = draft.level_delta
            tank.update_period = draft.update_period
            refresh_live()

        ui.button('Apply Changes', on_click=apply_draft_values).classes('w-24')

    ui.separator()
    ui.markdown('### Live object')
    live = ui.code('').classes('w-full max-w-3xl')

    def refresh_live() -> None:
        live.set_content('\n'.join(f'{k}: {v}' for k, v in tank.as_dict().items()))

    refresh_live()
    ui.timer(0.2, refresh_live)

def main():
    # Note: reload=True causes 2 instances of the tank controller to run, which is bad
    ui.run(title='Virtual Level Controller', reload=False,port=controller.controller_ip_port)

if __name__ in {'__main__', '__mp_main__'}:
    print(controller.as_config('yaml'))
    print(controller.name)
    run_cycle = Thread(target=cycle_task,daemon=True,args=(tank,))
    run_cycle.start()
    main()
