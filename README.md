# virtual_watertank
A simple simulated watertank and level controller that run in containers, with web-based display/UI. 

author: Rich Moore - rmoorewrs@gmail.com

![HTTP Display](doc_img/tank-and-controller.gif)


There are 3 ways to run this project:
- docker compose
- kubernetes
- native python/local

## Requirements
### Clone this repo
For all use cases, clone this repo first
```
git clone https://github.com/rmoorewrs/virtual_watertank.git
```
---

### Docker Compose Requirements
- docker and docker-compose
- membership in the docker group so you can run docker without root
```
sudo usermod -aG docker <your_username>
newgrp docker
docker run --rm hello-world # this should work without sudo
```
>Note: depending on your distro and how docker was installed you may have to use `docker compose` or `docker-compose`

---
### Kubernetes Requirements
- kubernetes cluster that can access the internet
- kubectl 
- one single yaml file from this repo `./k8s/vwt_deploy.yaml`

---
### Native Python/Local Requirements
To run the project with native python (i.e. not in a container) you'll need more packages: 
- python 3.x
- python venv
- curl
>See the Optional section below on how to run the apps locally. 

---
## Docker Compose Instructions

### Build the containers
```
cd virtual_watertank
./build_containers.sh
```
>Optional: To build the Node Red container
```
cd nodered
./build_containers.sh  # this will build all 3 containers
```

### Start the project
```
cd virtual_watertank
docker compose up 
# or
docker-compose up
```
>Optional: To include the Node Red container
To run with the Node Red container
```
cd nodered
docker compose up
```

### Observe the Tank and controller in a browser
Open browser windows: 
- http://localhost:5050   # this is the virtual watertank display
- http://localhost:5051   # this is the virtual level controller UI
- http://localhost:1880   # Optional if you're running the Node Red container

### Shutdown
```
cd virtual_watertank
docker compose down 
# or
docker-compose down
```

---

### Running in Kubernetes
To start the project, apply the combined project file `./k8s/vwt_deploy.yaml`
```
kubectl apply -f vwt_project.yaml
```
This will start 3 pods and 3 servcies:
- watertank
- levelcontroller
- nodered

The container UIs should be available after a short time as node ports on whichever node is running the pods. For example, if the node IP address is `10.10.10.2`
```
http://10.10.10.2:30050 -- Watertank
http://10.10.10.2:30051 -- Levelcontroller
http://10.10.10.2:30880 -- NodeRed UI
```

---

### Running Native Python Locally (i.e. not in container): 

#### First set up a virtual environment:
```
cd  # into top level of git repo
mkdir .venv
python3 venv .venv
./venv/bin/activate
pip install -r requirements.txt
```
When you want to exit the virtual environment, just type `deactivate`

#### Copy and edit the config.yaml file
```
cp <git_repo_directory>/config/local/config.yaml .
```
Optional: Edit the ports to work for your setup, or leave the defaults

#### Run the Tank first
From the top level git directory
```
source .venv/bin/activate
python3 src/virtual_watertank/virtual_watertank.py --config ./config.yaml
```
Open browser to the port specified in `config/local/config.yaml` i.e. `5050`

#### Run the Level Controller
Open another shell and cd into the top level of the git repo
```
source .venv/bin/activate
python3 src/virtual_levelcontroller/virtual_controller.py --config ./config.yaml
```

> Note: running Node Red natively isn't covered here

---
---

# API Documentation

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
---
---