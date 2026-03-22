# virtual_watertank
A simple simulated watertank and level controller that run in containers, with web-based display. 

author: Rich Moore - rmoorewrs@gmail.com

![HTTP Display](https://github.com/rmoorewrs/virtual_watertank/blob/main/doc_img/tank-animation.gif)

## Requirements
- docker and docker-compose
- preferably membership in the docker group so you can run docker without root
```
sudo usermod -aG docker <your_username>
newgrp docker
docker run --rm hello-world # this should work without sudo
```

By default the project creates two containers and they're started by docker-compose. So that's really it unless you intend to run the applications locally, and then you'll need more packages: 
- python 3.x
- python venv
- curl

>See the Optional section below on how to run the apps locally. 

## Instructions

1) Clone this repo

```
git clone https://github.com/rmoorewrs/virtual_watertank.git
```

2) Build the containers
```
cd virtual_watertank
./build_containers.sh
```

3) Run the tank container

```
cd virtual_watertank
docker compose up 
# or
docker-compose up
```

4) Observe the Tank in a browser

Open two browser windows: 
- http://localhost:5050   # this is the virtual watertank display
- http://localhost:5051   # this is the virtual level controller UI

5) Stop the Tank
```
cd virtual_watertank
docker compose down 
# or
docker-compose down
```

### Optional: 
If you want to run the python applications locally then set up a virtual environment:
```
cd  # into top level of git repo
mkdir .venv
python3 venv .venv
./venv/bin/activate
pip install -r requirements.txt
```
When you want to exit the virtual environment, just type `deactivate`

>NOTE: you will need to edit the IP address in `src/virtual_levelcontroller/virtual_levelcontroller.py` since it assumes running in docker compose with a service named `watertank` 

### Test the API using curl

#### Get tank level:

```
curl http://localhost:5050/level
```
Expected Response (example):
```
{
    "level": 26
}
```


#### Set tank level (force level):

```
curl -X POST http://localhost:5050/level -H "Content-Type: application/json" -d '{"level": 75}'
```
Expected Response (example):
```
{
    "level": 75
}
```
#### Drain water from the tank:

Example: drain 1% of the water
```
 curl -X POST http://localhost:5050/drain -H "Content-Type: application/json" -d '{"delta_level": 1}'
```
Expected Response (example):
```
{
    "level": 73,
    "mode": "drain"
}
```
#### Add water to the tank:

Example: add 1% of tank's capacity
```
 curl -X POST http://localhost:5050/fill -H "Content-Type: application/json" -d '{"delta_level": 1}'
```
Expected Response (example):
```
{
    "level": 74,
    "mode": "fill"
}
```

#### Get an image showing the current tank level:
```
curl http://localhost:5050/image --output /tmp/current_tank_level.webp
```
