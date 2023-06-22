FROM python:3.12.0b3-alpine3.17 AS builder
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && pip3 install --user --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12.0b3-alpine3.17
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local:$PATH
COPY pihole-to-influxdb2.py /pihole-to-influxdb2.py
COPY healthcheck /healthcheck
ENV VERBOSE="false" 
ENV RUN_EVERY_SECONDS="10" 
ENV INFLUX_HOST="IP_OR_NAME" 
ENV INFLUX_PORT="PORT" 
ENV INFLUX_ORGANIZATION="ORGANIZATION" 
ENV INFLUX_BUCKET="BUCKET" 
ENV INFLUX_TOKEN="TOKEN" 
ENV PIHOLE_HOSTS="ip1:port1:name1:token1,ip2:port2:name2:token2" 
ENV INFLUX_SERVICE_TAG="pihole"
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
            CMD grep OK /healthcheck || exit 1
ENTRYPOINT [ "python", "/pihole-to-influxdb2.py" ]
