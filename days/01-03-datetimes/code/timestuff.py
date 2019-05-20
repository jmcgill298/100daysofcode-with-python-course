#! /usr/bin/env python
import re
import yaml
from datetime import datetime
from datetime import timedelta

try:
    from textfsm.parser import TextFSM
except ImportError:
    from textfsm import TextFSM


CURRENT_TIME = datetime.now()
RE_UPTIME = re.compile("(?P<time>\d+)(?P<measurement>\w)")
UPTIME_MAP = {
    "m": "months",
    "w": "weeks",
    "d": "days",
    "h": "hours",
}

def convert_rib_to_dict(fsm_results):
    """
    """
    new_results = {}
    for entry in fsm_results:
        network = f"{entry['network']}/{entry['mask']}"
        if new_results.get(network) is None:
            new_results[network] = [entry]
        else:
            new_results[network].append(entry)
    return new_results


def convert_uptime_to_timedelta(uptime):
    """
    """
    uptime_data = {}
    if ":" in uptime:
        uptime_values = uptime.split(":")
        uptime_measurements = ("hours", "minutes", "seconds")
    elif "." in uptime:
        uptime_values = uptime.split(".")
        uptime_values.pop()
        uptime_measurements = ("seconds",)
    else:
        uptime_parsed = RE_UPTIME.findall(uptime)
        uptime_parsed_copy = uptime_parsed.copy()
        for entry, time_data in enumerate(uptime_parsed_copy):
            if time_data[1] == "y":
                uptime_parsed.pop(entry)
                uptime_parsed.append((int(time_data[0]) * 365, "d"))
        uptime_values = (value for value, measurement in uptime_parsed)
        uptime_measurements = (UPTIME_MAP[measurement] for value, measurement in uptime_parsed)

    uptime_int_values = (int(value) for value in uptime_values)
    uptime_data = dict(zip(uptime_measurements, uptime_int_values))
    return timedelta(**uptime_data)


def convert_timedelta_to_datetime(time_delta):
    """
    """
    return CURRENT_TIME - time_delta


with open("cisco_nxos_show_ip_route.template") as template:
    fsm = TextFSM(template)

with open("cisco_nxos_show_ip_route.raw") as cli_output:
    cli_parsed = fsm.ParseText(cli_output.read())

current_rib = [dict(zip(fsm.header, entry)) for entry in cli_parsed]
with open("cisco_nxos_show_ip_route.yml") as previous:
    previous_rib = yaml.safe_load(previous)

previous_as_dict = convert_rib_to_dict(previous_rib)
current_as_dict = convert_rib_to_dict(current_rib)

flapped_routes = []
for previous_network, previous_routes in previous_as_dict.items():
    current_routes = current_as_dict.get(previous_network)
    if current_routes is not None:
        for previous_route in previous_routes:
            for current_route in current_routes:
                if (
                    previous_route["nexthop_ip"] == current_route["nexthop_ip"]
                    and previous_route["nexthop_if"] == current_route["nexthop_if"]
                    and previous_route["nexthop_vrf"] == current_route["nexthop_vrf"]
                ):
                    previous_uptime = convert_uptime_to_timedelta(previous_route["uptime"])
                    current_uptime = convert_uptime_to_timedelta(current_route["uptime"])
                    if current_uptime < previous_uptime:
                        current_route["timedelta"] = current_uptime
                        flapped_routes.append(current_route)

for route in flapped_routes:
    flap_time = convert_timedelta_to_datetime(route["timedelta"])
    print(
        f"Network {route['network']}/{route['mask']}, "
        f"using destination {route['nexthop_if']} {route['nexthop_ip']}, "
        f"flapped and last returned at {flap_time}"
    )
