FROM debian:13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nfdump ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data
EXPOSE 9996/udp

CMD ["nfcapd", "-E", "-p", "9996", "-t", "60", "-l", "/data"]
