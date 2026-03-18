FROM elxrlinux/elxr:12.12.0.0

EXPOSE 80 443 5000 5001

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Options::="--force-confnew" -qy install --no-install-recommends \
    python3 \
    python3-flask \
    python3-flask-restful \
    python3-pil \
    tini


# create non-root user
RUN /usr/sbin/useradd -m --shell /bin/bash wruser

# Copy the app
WORKDIR /home/wruser
COPY  ./virtual_watertank.py .
COPY ./launch.sh .
COPY ./static ./static/
COPY ./templates ./templates/

RUN chown -R wruser:wruser /home/wruser

# tini runs in single child mode by default, -g sets group mode
ENTRYPOINT ["/usr/bin/tini","-g"]

CMD [ "/bin/sh", "launch.sh" ]

USER wruser