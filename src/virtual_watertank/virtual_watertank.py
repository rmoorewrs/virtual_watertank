import os
import argparse
from flask import Flask, render_template, send_file, abort
from flask_restful import Api, Resource, reqparse
from io import BytesIO
from PIL import Image
from pathlib import Path
import yaml
import uuid

app = Flask(__name__)
api = Api(app)

# In-memory store for level (use a DB or file in production)
""" 
level - 0-100 integer representing percentage of full
mode - can be either fill | drain
"""
MYID = uuid.uuid4()
MYNAME = f"Tank_"+ MYID.hex[-4:]
CONFIG_FILENAME = 'config.yaml'
WATERTANK_URL = '12.7.0.0.1'
WATERTANK_PORT = '5050'

mode_types = ['drain','fill']
tank_state = {'level': 0,'mode': 'drain','uuid':MYID.hex,'name':MYNAME}
current_image_filename = 'D000.webp'

class Config:
    config_file = None
    tank_config = None
    tank_ip_address = None
    tank_ip_port = None
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

            self.tank_config = config_data.get('watertank', config_data)
            self.tank_ip_address = self.tank_config.get('tank_ip_address',WATERTANK_URL)
            self.tank_ip_port = self.tank_config.get('tank_ip_port',WATERTANK_PORT)

        self.name = self.tank_config.get('name',MYNAME)
        self.uuid = self.tank_config.get('uuid',uuid.uuid4())
        self.name = f'{self.name}-{str(self.uuid)[-4:]}'

    def as_dict(self) -> dict[str, int | bool]:
        return {
            'tank_ip_address': self.tank_ip_address,
            'tank_ip_port': self.tank_ip_port,
            'name': self.name,
            'uuid': self.uuid
        }

    def as_config(self, format: str = 'json') -> str:
        config = {
            'watertank': {
                'tank_ip_address': self.tank_ip_address,
                'tank_ip_port': self.tank_ip_port,
            }
        }

# parsing validator (hopefully)
def force_valid_range(value):
    """Validator for 0-100 range."""
    num = int(value)
    if num <= 0:
        num = 0
    elif num > 100:
        num = 100
    return num

def compute_current_filename(level,mode):
    valid_level=force_valid_range(level)
    padded = f"{int(valid_level):03d}"
    if (mode == 'fill'):
        image_filename = f"F{padded}.webp"
    else:
        image_filename = f"D{padded}.webp"
    return image_filename

def return_current_image(image_filename):
    """Return the currently displayed level image as a WebP file."""
    image_path = os.path.join(app.root_path, "static", "img", image_filename)

    if not os.path.exists(image_path):
        abort(404, description="Image for current level not found.")

    with Image.open(image_path) as img:
        buffer = BytesIO()
        img.save(buffer, format="WEBP")
        buffer.seek(0)

    return send_file(
        buffer,
        mimetype="image/webp",
        download_name=f"current_image.webp",
        as_attachment=False,
    )

class Fill(Resource):
    def get(self):
        """Return the current level value."""
        tank_state['mode'] = 'fill'
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201
    
    def post(self):
        """Add water to the tank, minimum 1% or integer 1"""
        parser = reqparse.RequestParser()
        parser.add_argument(
            'delta_level', 
            type=force_valid_range,
            required=True, 
            help="delta_level must be an integer between 0 and 100"
            )
        args = parser.parse_args()
        tank_state['mode'] = 'fill'
        tank_state['level'] = force_valid_range(tank_state['level'] + args['delta_level'])
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201


class Drain(Resource):
    def get(self):
        """Return the current level value."""
        tank_state['mode'] = "drain"
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201
    
    def post(self):
        """Drain water from the tank, minimum 1% or integer 1"""
        parser = reqparse.RequestParser()
        parser.add_argument(
            'delta_level', 
            type=force_valid_range,
            required=True, 
            help="delta_level must be an integer between 0 and 100"
            )
        args = parser.parse_args()
        tank_state['mode'] = "drain"
        tank_state['level'] = force_valid_range(tank_state['level'] - args['delta_level'])
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201


class Level(Resource):
    def get(self):
        """Return the current level value."""
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201

    def post(self):
        """Set the level to an integer value."""
        parser = reqparse.RequestParser()
        parser.add_argument(
            'level', 
            type=force_valid_range,
            required=True, 
            help="level must be an integer between 0 and 100"
            )

        args = parser.parse_args()
        tank_state['level'] = args['level']
        return {'level': tank_state['level'],'mode': tank_state['mode'],'uuid':tank_state['uuid'],'name':tank_state['name']}, 201


class CurrentImage(Resource):
    def get(self):
        current_image_filename = compute_current_filename(tank_state['level'],tank_state['mode'])
        return return_current_image(current_image_filename)
    
class TankUUID(Resource):
    def get(self):
        return tank_state['uuid']
    
class TankName(Resource):
    def get(self):
        return tank_state['name']


# helper to parse command line arguments
def parse_startup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Virtual Water Tank')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to YAML config file (default: config.yaml)',
    )
    args, _unknown = parser.parse_known_args()
    return args


# create objects
startup_args = parse_startup_args()
config = Config(startup_args.config)


# API endpoints
api.add_resource(Level, '/level')
api.add_resource(Fill,'/fill')
api.add_resource(Drain,'/drain')
api.add_resource(CurrentImage, '/image')
api.add_resource(TankUUID, '/uuid')
api.add_resource(TankName,'/name')


@app.route('/')
def index():
    """Display the level in an HTML page."""
    return render_template("watertank.html", level=tank_state['level'],mode=tank_state['mode'])


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True,port=config.tank_ip_port)
