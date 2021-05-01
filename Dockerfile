FROM python:3.9.4-alpine
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && pip3 install --no-cache-dir -r /tmp/requirements.txt
COPY pihole-to-influxdb2.py /pihole-to-influxdb2.py
COPY healthcheck /healthcheck
ENV VERBOSE="false" 
ENV RUN_EVERY_SECONDS="10" 
ENV INFLUX_HOST="IP_OR_NAME" 
ENV INFLUX_PORT="PORT" 
ENV INFLUX_ORGANIZATION="ORGANIZATION" 
ENV INFLUX_BUCKET="BUCKET" 
ENV INFLUX_TOKEN="TOKEN" 
ENV PIHOLE_HOSTS="ip1:port1:name1,ip2:port2:name2" 
ENV INFLUX_SERVICE_TAG="pihole"
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
            CMD grep OK /healthcheck || exit 1
ENTRYPOINT [ "python", "pihole-to-influxdb2.py" ]
