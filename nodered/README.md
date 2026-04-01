# Running Node Red
The Dockerfile in this directory adds some extra packages to enable PLC ladder logic and Modbus/TCP industrial protocol for experimentation. 

The conatiner image isn't built by default by the top-level `build_containers.sh` script, but the one here builds all 3 containers and stores them in the local cache. 

>If you make changes to the Node Red flows and deploy them, they will be stored in `./data` which you can back up to another location for future use. If you build the containers again, the contents of `./data` will be copied into the nodered container image in your local cache.  

To build containers:
```
cd virtual_watertank/nodered
./build_containers.sh
```

To start project
```
cd virtual_watertank/nodered
docker compose up
```