FROM python:3.7

RUN pip install aiohttp cchardet aiodns asyncio-nats-client requests

RUN DEBIAN_FRONTEND=noninteractive apt-get update -y && \
  DEBIAN_FRONTEND=noninteractive apt-get install git

RUN git clone https://github.com/arubaiberia/agora.git /opt/agora

WORKDIR /opt/agora/python

ENTRYPOINT ["/usr/local/bin/python"]
