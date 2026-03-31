# Running Node Red
The Dockerfile in this directory adds some extra packages to enable PLC ladder logic and Modbus/TCP industrial protocol for experimentation. 

The conatiner image isn't built by default by the top-level `build_containers.sh` script, but the one here builds all 3 containers and stores them in the local cache. 

To build containers:
```
cd virtual_watertank/nodered
./build_containers.sh
```

To run containers with docker-compose
```
docker compose -f docker-compose.nodered .
```