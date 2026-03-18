FROM elxrlinux/elxr:12.12.0.0

EXPOSE 80 443 5000 8080

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Options::="--force-confnew" -qy install --no-install-recommends \
    python3 \
    python3-pip \
    python3-requests \
    tini

RUN pip install --break-system-packages nicegui

# create non-root user
RUN /usr/sbin/useradd -m --shell /bin/bash wruser

# Copy the app
WORKDIR /home/wruser
COPY  ./virtual_controller.py .
COPY ./launch.sh .

RUN chown -R wruser:wruser /home/wruser

# tini runs in single child mode by default, -g sets group mode
ENTRYPOINT ["/usr/bin/tini","-g"]

CMD [ "/bin/sh", "launch.sh" ]

USER wruser