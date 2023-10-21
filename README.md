# Pihole2InfluxDB2

## Changelog

* **1.7**: upgraded Python base image to 3.9.5-alpine
* **1.8**: upgraded Python base image to 3.10.0rc1-alpine
* **1.8.1**: upgraded Python base image to 3.10.0-alpine
* **1.8.2**: upgraded Python base image to 3.10.2-alpine3.15
* **1.8.3**: upgraded Python base image to 3.11.0a6-alpine3.15 and improved Pi-hole API Error handling
* **1.8.4**: fixed an exception when remote Pi-hole FTL is not running
* **1.8.5**: upgraded Python base image to 3.11.0b3-alpine3.15
* **1.8.6**: upgraded Python base image to 3.11.0rc2-alpine3.16
* **2.0**: Breaking change: [API Token required now](https://pi-hole.net/blog/2022/11/17/upcoming-changes-authentication-for-more-api-endpoints-required/) - Upgraded Python base image to 3.11-alpine3.17
* **2.0.2**: fixed problems with integers uploaded as strings
* **2.0.3**: upgraded Python base image to 3.11.2-alpine3.17
* **2.0.4**: forced setuptools>=65.5.1 due to vulnerabilities
* **2.0.5**: upgraded Python base image to 3.12.0-alpine3.18

## Info

You can find my series of articles about my pihole/unbound setup monitored via pihole2influxdb2 and unbound2influxdb2 at the following page:
<http://giannicostanzi.medium.com>

## Sources

You can find Dockerfile and pihole-to-influxdb2.py sources on GitHub:
<https://github.com/MightySlaytanic/pihole2influxdb2>

## Docker Hub Image

<https://hub.docker.com/repository/docker/giannicostanzi/pihole2influxdb2>

## Base Image

The base image is the official *python:3.x.y-alpine* on top of which we install *influxdb_client* (via *pip*).

## Environment Variables

| Variable | Values |Default|
|-------------|-----------|-----------|
| INFLUX_HOST|IP, DNS or Docker Container/Service name of InfluxDB2 Server |IP_OR_NAME *// must be changed //*|
| INFLUX_PORT|Port on which InfluxDB2 server is listening, usually 8086 |PORT *// must be changed //*|
| INFLUX_ORGANIZATION| Organization set in InfluxDB2 |ORGANIZATION *// must be changed //*|
| INFLUX_BUCKET | Bucket on InfluxDB2 server where measurements will be stored |BUCKET *// must be changed //*|
| INFLUX_TOKEN | InfluxDB2 access token to write data on *INFLUX_BUCKET* |TOKEN *// must be changed //*|
| INFLUX_SERVICE_TAG | Name assigned to the *service* tag assigned to every record sent to InfluxDB2 | pihole
| PIHOLE_HOSTS | Comma separated list of Pi-hole hosts definition, each of which is written in format *IP_OR_NAME:PORT:APITOKEN:HOST_TAG*"|ip1:port1:token1:name1,ip2:port2:token2:name2 *// must be changed //*|
| RUN_EVERY_SECONDS | Pi-hole polling time | 10
| VERBOSE | Increase logging output (not so verbose BTW) |false

*PIHOLE_HOSTS*: this variable can be set for example to *192.168.0.1:50080:APITOKEN1:rpi2,raspberry.home:80:APITOKEN2:rpi3,pihole-container:80:APITOKEN3:pi-container* which in turn configures the container to poll every *RUN_EVERY_SECONDS* the following Pi-hole servers:

* 192.168.0.1 which listens with http GUI on 50080/TCP and using rpi2 as *host* tag attached to the data sent to InfluxDB2
* raspberry.home (DNS name) which listens on 80/TCP and using rpi3 as *host* tag
* pihole-container which listens on 80/TCP and using pi-container as *host* tag. In this case *pihole-container* must be a container running on the same *non-default bridge network* on which this *pihole2influxdb2* container is running in order to have docker's name resolution working as expected and the port specified is the default 80/TCP port on which pihole official image is listening, not the port on which you expose it.

*API TOKEN*: from v2.0 of this image it is required to specify the API TOKEN to query pihole servers. API Token can be found in the GUI
under Settings -> API/WEB Interface -> Show API Token

## Usage example

You can specify *-t* option which will be passed to **/pihole-to-influxdb2.py** within the container to output all the values obtained from pihole servers to screen, without uploading nothing to the influxdb server. Remember to specify *-t* also as *docker run* option in order to see the output immediately (otherwise it will be printed on output buffer flush)

```bash
docker run -t --rm \
-e INFLUX_HOST="influxdb_server_ip" \
-e INFLUX_PORT="8086" \
-e INFLUX_ORGANIZATION="org-name" \
-e INFLUX_BUCKET="bucket-name" \
-e INFLUX_TOKEN="influx_token" \
-e PIHOLE_HOSTS="ip1:port1:token1:tag_name1,ip2:port2:token2:tag_name2" \
pihole2influxdb2 -t
```

If you remove the *-t* option passed to the container, collected data will be uploaded to influxdb bucket in two measurements, *stats* and *gravity*. The following is an example of a non-debug run:

```bash
docker run -d  --name="pihole2influxdb2-stats" \
-e INFLUX_HOST="192.168.0.1" \
-e INFLUX_PORT="8086" \
-e INFLUX_ORGANIZATION="org-name" \
-e INFLUX_BUCKET="bucket-name" \
-e INFLUX_TOKEN="XXXXXXXXXX_INFLUX_TOKEN_XXXXXXXXXX" \
-e PIHOLE_HOSTS="192.168.0.2:50080:TOKEN1:rpi3,192.168.0.3:80:TOKEN2:rpi4" \
-e RUN_EVERY_SECONDS="60" \
-e INFLUX_SERVICE_TAG="my_service_tag" \
pihole2influxdb2
```

These are the *fields* uploaded for *stats* measurement (I'll show the influxdb query used to view them all):

```flux
from(bucket: "test-bucket")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "stats")
|> filter(fn: (r) => r["_field"] == "ads_blocked_today" 
    or r["_field"] == "ads_percentage_today" 
    or r["_field"] == "clients_ever_seen" 
    or r["_field"] == "dns_queries_all_types" 
    or r["_field"] == "dns_queries_today" 
    or r["_field"] == "domains_being_blocked" 
    or r["_field"] == "privacy_level" 
    or r["_field"] == "queries_cached" 
    or r["_field"] == "queries_forwarded" 
    or r["_field"] == "reply_CNAME" 
    or r["_field"] == "reply_IP" 
    or r["_field"] == "reply_NODATA" 
    or r["_field"] == "reply_NXDOMAIN" 
    or r["_field"] == "status" 
    or r["_field"] == "unique_clients" 
    or r["_field"] == "unique_domains")
```

These are the fields uploaded for *gravity* measurement:

```flux
from(bucket: "test-bucket")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "gravity")
|> filter(fn: (r) => r["_field"] == "file_exists" 
    or r["_field"] == "seconds_since_last_update")
```

Each record has also a tag named *host* that contains the names passed in *PIHOLE_HOSTS* environment variable and a *service* tag named as the *INFLUX_SERVICE_TAG* environment variable.

## Healthchecks

Starting from tag 1.3 I've implemented an healthcheck that sets the container to unhealthy as long as there is at least one Pi-hole server that can't be queried or if there are problems uploading stats to influxdb2 server.
For example, I launch a container with pihole2influxdb2:1.3 image and everything is ok, the container is healthy after 30 seconds:

```bash
$ docker ps
CONTAINER ID   IMAGE                                 COMMAND                  CREATED          STATUS                             PORTS                                            NAMES
22ff98ab4475   giannicostanzi/pihole2influxdb2:1.3   "python pihole-to-in…"   11 seconds ago   Up 10 seconds (health: starting)                                                    exciting_perlman

$ docker ps
CONTAINER ID   IMAGE                                 COMMAND                  CREATED          STATUS                    PORTS                                            NAMES
22ff98ab4475   giannicostanzi/pihole2influxdb2:1.3   "python pihole-to-in…"   32 seconds ago   Up 30 seconds (healthy)                                                    exciting_perlman
```

Now I restart Pi-hole on raspberry, and after some seconds it becomes unhealthy (it can take up to 90 seconds with the new health-check parameters to detect an unhealthy status):

```bash
$ docker ps 

CONTAINER ID   IMAGE                                 COMMAND                  CREATED              STATUS                          PORTS                                            NAMES
22ff98ab4475   giannicostanzi/pihole2influxdb2:1.3   "python pihole-to-in…"   About a minute ago   Up About a minute (unhealthy)                                                    exciting_perlman
```

I can see from the logs what is the cause of the unhealthiness:

```bash
$ docker logs 22ff98ab4475

<urlopen error [Errno 111] Connection refused>
URLError: Could not connect to 192.168.0.2:50080(raspberry)
```

When Pi-hole is active again, the container goes back to healthy state:

```bash
$ docker ps
CONTAINER ID   IMAGE                                 COMMAND                  CREATED         STATUS                   PORTS                                            NAMES
22ff98ab4475   giannicostanzi/pihole2influxdb2:1.3   "python pihole-to-in…"   3 minutes ago   Up 3 minutes (healthy)                                                    exciting_perlman
```

**Note:** if you have problems with the healthcheck not changing to unhealthy when it should (you see errors in the logs, for example) have a look at the health check reported by *docker inspect CONTAINER_ID* if matches the following one:

```yaml
"Healthcheck": {
  "Test": [
    "CMD-SHELL",
    "grep OK /healthcheck || exit 1"
  ],
  "Interval": 30000000000,
  "Timeout": 3000000000,
  "Retries": 3
}
```

If it doesn't, it could be the previous healthcheck used before tag 1.3 which wasn't working. I'm using *Watchtower* container to update my containers automatically and I've seen that my *pihole2influxdb2* container has been updated to 1.3.2 but healthcheck was still the old one, so I've recreated the container by hand and it worked as expected.
