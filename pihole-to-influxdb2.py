#!/usr/bin/python3
import sys
import json
import argparse
import urllib.request
from urllib.error import URLError
from datetime import datetime
from time import sleep
from os import getenv
from os.path import realpath, dirname

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

PROGRAM_DIR = dirname(realpath(__file__))
HEALTHCHECK_FILE = f"{PROGRAM_DIR}/healthcheck"
HEALTHCHECK_FAILED = "FAILED"
HEALTHCHECK_OK = "OK"

INFLUX_HOST = getenv("INFLUX_HOST")
INFLUX_PORT = getenv("INFLUX_PORT")
INFLUX_ORGANIZATION = getenv("INFLUX_ORGANIZATION")
INFLUX_BUCKET = getenv("INFLUX_BUCKET")
INFLUX_TOKEN = getenv("INFLUX_TOKEN")
INFLUX_SERVICE_TAG = getenv("INFLUX_SERVICE_TAG")
PIHOLE_HOSTS = getenv("PIHOLE_HOSTS")
RUN_EVERY_SECONDS = int(getenv("RUN_EVERY_SECONDS"))
VERBOSE = getenv("VERBOSE")

DEBUG = 0


def set_failed_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_FAILED)


def set_ok_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_OK)

    
if __name__ == '__main__':
    if VERBOSE.lower() == "true":
        DEBUG = 1

    PIHOLE_HOSTS_DICT = {}

    for index, entry in enumerate(PIHOLE_HOSTS.split(",")):
        try:
            host, port, name = entry.split(":")
        except ValueError as e:
            print(e, file=sys.stderr)
            print(f"Wrong PIHOLE_HOSTS entry <{entry}>!", file=sys.stderr)
            sys.exit(1)

        PIHOLE_HOSTS_DICT.update({ index : { "host": host, "name": name, "port": port } })

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting...")
    print("\nPIHOLE_HOSTS definition:\n")
    print(json.dumps(PIHOLE_HOSTS_DICT, indent=4))

    if DEBUG:        
        print(f"\nHealthcheck file => {HEALTHCHECK_FILE}")

    parser = argparse.ArgumentParser(usage="PiHole Stats to influxdb2 uploader")

    parser.add_argument(
        "-t",
        "--test",
        help="Just print the results without uploading to influxdb2",
        action="store_true"
    )

    args = parser.parse_args()

    last_healthcheck_failed = False
    set_ok_flag()

    while True:
        start_time = datetime.now()
        failure = False

        for index in PIHOLE_HOSTS_DICT.keys():
            host = PIHOLE_HOSTS_DICT[index]["host"]
            host_name = PIHOLE_HOSTS_DICT[index]["name"]
            host_port = PIHOLE_HOSTS_DICT[index]["port"]

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting data for host {host}:{host_port}({host_name})...")

            try:
                with urllib.request.urlopen(f"http://{host}:{host_port}/admin/api.php", timeout=10) as url:
                    stats = json.loads(url.read().decode())
            except URLError as e:
                failure = True
                print(e,file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] URLError: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if args.test:
                print(f"\nStats for host {host}:{host_port}({host_name}): ")
                print(json.dumps(stats, indent=4))
            
            else:
                gravity_last_updated = stats.pop("gravity_last_updated")
                gravity_file_exists = gravity_last_updated["file_exists"]
                gravity_seconds_since_last_update = \
                    gravity_last_updated["relative"]["minutes"] * 60 \
                    + gravity_last_updated["relative"]["hours"] * 3600 \
                    + gravity_last_updated["relative"]["days"] * 86400

                stats["ads_percentage_today"] = float(stats["ads_percentage_today"])

                try:
                    if DEBUG:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uploading data for host {host}({host_name})...")
                    client = InfluxDBClient(url=f"http://{INFLUX_HOST}:{INFLUX_PORT}", token=INFLUX_TOKEN, org=INFLUX_ORGANIZATION, timeout=10)
                    write_api = client.write_api(write_options=SYNCHRONOUS)

                    write_api.write(
                        INFLUX_BUCKET,
                        INFLUX_ORGANIZATION,
                        [
                            {
                                "measurement": "stats",
                                "tags": {"host": host_name, "service":INFLUX_SERVICE_TAG},
                                "fields": stats
                            },
                            {
                                "measurement": "gravity",
                                "tags": {"host": host_name, "service":INFLUX_SERVICE_TAG},
                                "fields": {
                                    "file_exists": gravity_file_exists,
                                    "seconds_since_last_update": gravity_seconds_since_last_update
                                }
                            }
                        ]
                    )
                except TimeoutError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TimeoutError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                except InfluxDBError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] InfluxDBError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                except Exception as e:
                    failure = True
                    print(e, file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                finally:
                    client.close()
    
        # Health check management
        if failure:
            if not last_healthcheck_failed:
                # previous cycle was successfull, so we must set the failed flag
                set_failed_flag()
                last_healthcheck_failed = True
        else:
            if last_healthcheck_failed:
                # Everything ok, clear the flag
                set_ok_flag()
                last_healthcheck_failed = False

        # Sleep for the amount of time specified by RUN_EVERY_SECONDS minus the time elapsed for the above computations
        stop_time = datetime.now()
        delta_seconds = int((stop_time - start_time).total_seconds())
        
        if delta_seconds < RUN_EVERY_SECONDS:
            sleep(RUN_EVERY_SECONDS - delta_seconds)
