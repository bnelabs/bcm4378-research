#!/usr/bin/env python3
"""Sample host and Wi-Fi queues while fetching a small HTTPS object on macOS."""

import argparse
from contextlib import closing
from hashlib import sha256
import http.client
import json
from pathlib import Path
import re
import socket
from struct import pack, unpack
import subprocess
import sys
import time
from urllib.parse import urlsplit


# Values from the macOS SDK sys/socket.h.
SO_NET_SERVICE_TYPE = 0x1116
SO_NETSVC_MARKING_LEVEL = 0x1119
SO_MAX_PACING_RATE = 0x1136
SERVICE = {"BE": 0, "BK": 1, "VI": 3}
UNLIMITED = (1 << 64) - 1
BACKGROUND_CEILING = 125_000
BODY_LIMIT = 65_536
TIMEOUT = 20
SEQUENCE = ("idle", "BE", "VI", "BK", "idle", "BK", "VI", "BE", "idle")


def route(target, family=socket.AF_INET):
    family_flag = "-inet6" if family == socket.AF_INET6 else "-inet"
    output = subprocess.check_output(
        ["/sbin/route", "-n", "get", family_flag, target], text=True, timeout=5,
    )
    for row in output.splitlines():
        key, _, value = row.strip().partition(":")
        if key == "interface":
            return value.strip()
    raise ValueError("No interface in the route result")


def queue_counts(interface):
    output = subprocess.run(
        ["/usr/sbin/netstat", "-q", "-I", interface], capture_output=True, text=True, timeout=5,
    )
    if output.returncode != 0:
        return {}
    rows = {}
    group = None
    for line in output.stdout.splitlines():
        if match := re.search(r"\[ pri: (\S+)", line):
            group = match[1]
        if group and (match := re.search(r"dequeued pkts:\s*(\d+)\s+bytes:\s*(\d+)", line)):
            rows[group] = {"packets": int(match[1]), "bytes": int(match[2])}
    return rows


def snapshot(interfaces, reader):
    queues = {interface: queue_counts(interface) for interface in interfaces}
    sample = json.loads(subprocess.check_output([str(reader), "--wme"], timeout=8))
    radio = {}
    for row in sample["reports"]:
        name = row["name"].rsplit("Tid", 1)[-1]
        value = row.get("value")
        if isinstance(value, int):
            radio.setdefault(row["group"], {})[name] = value
    return {"queues": queues, "radio": radio, "link": sample["link"], "time": time.monotonic()}


def differences(before, after):
    return {
        counter: reading - before[counter] for counter, reading in after.items()
        if counter in before
    }


def read_object(connection, resource, wire):
    if connection.sock is not wire or wire.fileno() < 0:
        raise ValueError("The HTTPS server did not keep the test connection open")
    connection.request("GET", resource, headers={
        "Accept-Encoding": "identity", "User-Agent": "bcm4378-qos-check/1",
    })
    with connection.getresponse() as response:
        size = response.getheader("Content-Length")
        if response.status != 200 or (size is not None and int(size) > BODY_LIMIT):
            raise ValueError(f"Expected a successful HTTPS response of at most {BODY_LIMIT} bytes")
        payload = response.read(BODY_LIMIT + 1)
        if len(payload) > BODY_LIMIT or (size is not None and len(payload) != int(size)):
            raise ValueError("Unexpected HTTPS response size")
    if connection.sock is not wire or wire.fileno() < 0:
        raise ValueError("The HTTPS server closed the test connection")
    return {"body_bytes": len(payload), "body_sha256": sha256(payload).hexdigest()}


def configure(wire, service):
    limit = BACKGROUND_CEILING if service == "BK" else UNLIMITED
    wire.setsockopt(socket.SOL_SOCKET, SO_NET_SERVICE_TYPE, SERVICE[service])
    wire.setsockopt(socket.SOL_SOCKET, SO_MAX_PACING_RATE, pack("=Q", limit))
    service_readback = wire.getsockopt(socket.SOL_SOCKET, SO_NET_SERVICE_TYPE)
    pacing_readback, = unpack("=Q", wire.getsockopt(socket.SOL_SOCKET, SO_MAX_PACING_RATE, 8))
    if service_readback != SERVICE[service] or pacing_readback != limit:
        raise ValueError("Connected socket readback differs from the requested settings")
    return {
        "service_type": service_readback,
        "pacing_ceiling_bytes_per_second": None if limit == UNLIMITED else pacing_readback,
    }


def run(url, reader, wifi_interface):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None:
        raise ValueError("Supply an HTTPS URL without credentials")
    resource = parsed.path or "/"
    if parsed.query:
        resource += "?" + parsed.query

    default_before = route("default")
    with closing(http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=TIMEOUT)) as connection:
        connection.connect()
        wire = connection.sock
        peer = wire.getpeername()[0]
        target_route = route(peer, wire.family)
        interfaces = sorted({wifi_interface, target_route})
        warmup = read_object(connection, resource, wire)
        time.sleep(0.35)
        windows = []
        channel_context = None
        for service in SEQUENCE:
            before = snapshot(interfaces, reader)
            if channel_context is None:
                channel_context = before["link"]
            request = None
            if service == "idle":
                time.sleep(1.25)
            else:
                request = configure(wire, service)
                request.update(read_object(connection, resource, wire))
                request["marking_level_after_fetch"] = wire.getsockopt(socket.SOL_SOCKET, SO_NETSVC_MARKING_LEVEL)
                time.sleep(0.35)
            after = snapshot(interfaces, reader)
            if (before["link"] != channel_context or after["link"] != channel_context or
                channel_context["interface"] != wifi_interface or channel_context["primary_channel"] is None):
                raise ValueError("Wi-Fi channel context changed or was unavailable during a measurement")
            windows.append({
                "service": service,
                "request": request,
                "seconds": round(after["time"] - before["time"], 5),
                "link": after["link"],
                "host_queue_deltas": {
                    interface: {
                        group: differences(before["queues"][interface][group], counters)
                        for group, counters in after["queues"][interface].items()
                        if group in before["queues"][interface]
                    }
                    for interface in interfaces
                },
                "per_tid_deltas": {
                    group: differences(before["radio"][group], counters)
                    for group, counters in after["radio"].items() if group in before["radio"]
                },
            })
        target_after = route(peer, wire.family)
    default_after = route("default")
    if default_before != default_after or target_route != target_after:
        raise ValueError("Route changed during the measurement")
    return {
        "target_host": parsed.hostname,
        "target_route": target_route,
        "ipv4_default_before_and_after": [default_before, default_after],
        "wifi_interface": wifi_interface,
        "warmup_response": warmup,
        "windows": windows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Small HTTPS object on a server that supports keep-alive")
    parser.add_argument("--wme-reader", type=Path, required=True,
                        help="Compiled copy of tools/read_wifi_airtime.m")
    parser.add_argument("--wifi-interface", default="en0")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("The socket and queue interfaces require macOS")
    try:
        output = run(args.url, args.wme_reader.resolve(strict=True), args.wifi_interface)
    except (OSError, ValueError, subprocess.SubprocessError, http.client.HTTPException) as error:
        parser.error(str(error))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
