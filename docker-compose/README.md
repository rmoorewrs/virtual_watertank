# Docker compose options

## Use prebuilt images
If your system has internet access and you have issues building the images locally, you can use this `docker-compose.remote` file. It will pull the images from Docker Hub. 

```
docker compose -f docker-compose.remote up
```

This `docker-compose` file also mounts the `./config` directory to override the default config built into the container image. Note that if you change port numbers you need to do it both in the `config.yaml` and the `docker-compose.yaml` filed

## Network troubleshooting
If you have problems with networking, try attaching `netshoot` like this, after starting `docker compose`
```
docker run --rm -it --network virtual_watertank_default nicolaka/netshoot
```

If you want to capture a tcpdump file for wireshark, start the containers with this command:
```
docker compose -f docker-compose.netshoot up
```
It will capture the file into `./data`


