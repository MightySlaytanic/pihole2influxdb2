#!/bin/bash

export INFLUX_HOST="INFLUX_IP"
export INFLUX_PORT=8086
export INFLUX_ORGANIZATION="influx_org"
export INFLUX_BUCKET="influx_bucket"
export INFLUX_SERVICE_TAG="influx_service_tag"
export INFLUX_TOKEN="influx_token"
export PIHOLE_HOSTS="ip1:port1:tag1,ip2:port2:tag2"
export RUN_EVERY_SECONDS=10
export VERBOSE="True"

python3 ./pihole-to-influxdb2.py $*
