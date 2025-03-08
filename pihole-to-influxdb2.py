#!/usr/bin/python3

__author__ = "Gianni Costanzi <gianni DOT costanzi AT gmail DOT com>"
__version__ = "2.0.2"

import sys
import json
import argparse
import requests
from requests import HTTPError
from datetime import datetime
from time import sleep
from os import getenv
from os.path import realpath, dirname, isfile
from signal import signal, SIGTERM

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
PIHOLE_HOSTS_FILE = f"{PROGRAM_DIR}/etc/pihole_hosts"
RUN_EVERY_SECONDS = int(getenv("RUN_EVERY_SECONDS"))
VERBOSE = getenv("VERBOSE")

DEBUG = 0


def sigterm_handler(signum, frame):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SIGTERM received, shutting down..", file=sys.stderr)
    sys.exit(0)


def set_failed_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_FAILED)


def set_ok_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_OK)

    
if __name__ == '__main__':
    signal(SIGTERM, sigterm_handler)

    if VERBOSE.lower() == "true":
        DEBUG = 1

    PIHOLE_HOSTS_DICT = {}

    print(f"PIHOLE_HOSTS = <{PIHOLE_HOSTS}>")

    if PIHOLE_HOSTS == "file":
        # We expect to find Pi-hole hosts definitions in PIHOLE_HOSTS_FILE
        if isfile(PIHOLE_HOSTS_FILE):
            with open(PIHOLE_HOSTS_FILE, "r") as pihole_hosts_file:
                for index, pihole_hosts_dict in enumerate(json.load(pihole_hosts_file)):
                    # Check if all the info is contained in the dictionary
                    try:
                        PIHOLE_HOSTS_DICT.update({ index : { 
                                                            "host": pihole_hosts_dict["host"], 
                                                            "name": pihole_hosts_dict["name"], 
                                                            "port": pihole_hosts_dict["port"], 
                                                            "token": pihole_hosts_dict["password"]
                                                            } 
                                                  })

                    except KeyError as e:
                        print(f"Missing key {e} in entry #{index+1}", file=sys.stderr)
                        print(f"Wrong PIHOLE_HOSTS entry <index>:", file=sys.stderr)
                        print(json.dumps(pihole_hosts_dict, indent=4), file=sys.stderr)
                        sys.exit(1)
            if DEBUG:
                print(f"Imported hosts definitions from file {PIHOLE_HOSTS_FILE}")
        else:
            print(f"File {PIHOLE_HOSTS_FILE} not found!", file=sys.stderr)
            sys.exit(1)

    else:
        for index, entry in enumerate(PIHOLE_HOSTS.split(",")):
            try:
                host, port, token, name = entry.split(":")
            except ValueError as e:
                print(e, file=sys.stderr)
                print(f"Wrong PIHOLE_HOSTS entry <{entry}>!", file=sys.stderr)
                sys.exit(1)

            PIHOLE_HOSTS_DICT.update({ index : { "host": host, "name": name, "port": port, "token": token} })

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
            host_token = PIHOLE_HOSTS_DICT[index]["token"]

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting data for host {host}:{host_port}({host_name})...")

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authenticating on {host}:{host_port}({host_name})")

            try:
                auth_url = f"http://{host}:{host_port}/api/auth"
                auth_json = {}
                pwd_payload = { "password" : host_token }
                
                with requests.request("POST", auth_url, json=pwd_payload, verify=False) as auth_response:
                    auth_json = json.loads(auth_response.text)
            except HTTPError as e:
                failure = True
                print(e,file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTPError: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if "error" in auth_json:
                error=auth_json.pop("error")
                failure = True
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Authentication Error: <{error}> for {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if "session" in auth_json and not auth_json["session"]["valid"]:
                error=auth_json["session"]["message"]
                failure = True
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Invalid Session: <{error}> for {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Getting data from {host}:{host_port}({host_name})")

            try:
                headers = {
                    "X-FTL-SID": auth_json["session"]["sid"],
                    "X-FTL-CSRF": auth_json["session"]["csrf"]
                }
                stats_url = f"http://{host}:{host_port}/api/stats/summary"
                stats_json = {}
                with requests.request("GET", stats_url, headers=headers, data={}, verify=False) as stats_response:
                    stats_json = json.loads(stats_response.text)
            except HTTPError as e:
                failure = True
                print(e,file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTPError: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if "error" in stats_json:
                error=auth_json.pop("error")
                failure = True
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API stats/summary Error: <{error}> for {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Releasing session on {host}:{host_port}({host_name})")

            try:
                auth_url = f"http://{host}:{host_port}/api/auth"
                
                requests.request("DELETE", auth_url, json={}, headers=headers, verify=False)
            except HTTPError as e:
                failure = True
                print(e,file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTPError: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            
            if DEBUG:
                print(json.dumps(stats_json,indent=4))

            gravity_file_exists = True
            gravity_last_update = stats_json["gravity"]["last_update"]
            gravity_seconds_since_last_update = int((datetime.now() - datetime.fromtimestamp(gravity_last_update)).total_seconds())

            if gravity_last_update == 0:
                gravity_file_exists = False

            gravity = {
                "file_exists": gravity_file_exists,
                "seconds_since_last_update": gravity_seconds_since_last_update
            }
            
            queries = stats_json.pop("queries")
            clients = stats_json.pop("clients")

            stats = {
                "ads_percentage_today" : float(queries["percent_blocked"]),
                "queries_blocked" : int(queries["blocked"]),
                "queries_cached" : int(queries["cached"]),
                "queries_forwarded" : int(queries["forwarded"]),
                "clients_ever_seen" : int(clients["total"]),
                "clients_active" : int(clients["active"]),
                "domains_being_blocked" : int(stats_json["gravity"]["domains_being_blocked"]),
                "unique_domains" : int(queries["unique_domains"])
            }

            dns_replies_all_types = 0
            for key,value in queries["replies"].items():
                stats[f"reply_{key}"] = int(value)
                dns_replies_all_types += int(value)

            stats["dns_replies_all_types"] = dns_replies_all_types

            dns_queries_all_types = 0
            for key,value in queries["types"].items():
                stats[f"query_{key}"] = int(value)
                dns_queries_all_types += int(value)

            stats["dns_queries_all_types"] = dns_queries_all_types

            if args.test:
                print(f"\nStats for host {host}:{host_port}({host_name}): ")
                print(json.dumps(stats, indent=4))
                print(f"\nGravity for host {host}:{host_port}({host_name}): ")
                print(json.dumps(gravity, indent=4))
            
            else:
                try:
                    if DEBUG:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uploading data for host {host}({host_name})...")
                    client = InfluxDBClient(url=f"{INFLUX_HOST}:{INFLUX_PORT}", token=INFLUX_TOKEN, org=INFLUX_ORGANIZATION)
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
                                "fields": gravity
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
