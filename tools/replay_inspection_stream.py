#!/usr/bin/env python3
"""Compare two ways to send live inspection previews and a lossless archive."""

import argparse
from collections import deque
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import heapq
import json
from math import ceil
import socket
from struct import pack, unpack
import sys


FRAME_COUNT = 40
FRAME_INTERVAL_US = 200_000
PREVIEW_DEADLINE_US = 160_000
PREVIEW_BYTES = 2_048
ARCHIVE_BYTES = 40_960
CHUNK_BYTES = 4_096
# Segment end in microseconds and service in bytes per second.
LINK = ((2_000_000, 125_000), (3_200_000, 48_000), (None, 125_000))

# Darwin SDK sys/socket.h, also checked by probe_socket_qos.c.
SO_NET_SERVICE_TYPE = 0x1116
SO_MAX_PACING_RATE = 0x1136
BE, BK, VI = 0, 1, 3


@dataclass(frozen=True)
class Transfer:
    ready_us: int
    kind: str
    size: int


def delivery_time(now, size, link):
    remaining = size * 1_000_000
    for end, rate in link:
        if end is None:
            return now + (remaining + rate - 1) // rate
        if now >= end:
            continue
        capacity = (end - now) * rate
        if remaining <= capacity:
            return now + (remaining + rate - 1) // rate
        remaining -= capacity
        now = end
    raise ValueError("The replay link needs an open-ended final segment")


def replay(deadline_first, send_chunk=None, link=LINK):
    future = deque(
        Transfer(index * FRAME_INTERVAL_US, kind, size)
        for index in range(FRAME_COUNT)
        for kind, size in (("preview", PREVIEW_BYTES), ("archive", ARCHIVE_BYTES))
    )
    waiting = []
    order = 0
    now = 0
    previews = []
    expired = 0
    archived = 0
    archive_finished = 0
    while future or waiting:
        if not waiting:
            now = max(now, future[0].ready_us)
        while future and future[0].ready_us <= now:
            item = future.popleft()
            rank = int(deadline_first and item.kind == "archive")
            heapq.heappush(waiting, (rank, order, item.size, item))
            order += 1
        rank, index, remaining, item = heapq.heappop(waiting)
        chunk = min(remaining, CHUNK_BYTES)
        finished = delivery_time(now, chunk, link)
        if deadline_first and item.kind == "preview" and finished - item.ready_us > PREVIEW_DEADLINE_US:
            expired += 1
            continue
        if send_chunk is not None:
            send_chunk(item.kind, chunk)
        now = finished
        if chunk < remaining:
            heapq.heappush(waiting, (rank, index, remaining - chunk, item))
        elif item.kind == "preview":
            previews.append(now - item.ready_us)
        else:
            archived += item.size
            archive_finished = now

    sorted_delays = sorted(previews)
    return {
        "preview_offered": FRAME_COUNT,
        "preview_delivered": len(previews),
        "preview_by_deadline": sum(delay <= PREVIEW_DEADLINE_US for delay in previews),
        "preview_expired_before_send": expired,
        "preview_delivered_p95_ms": (
            round(sorted_delays[ceil(len(previews) * 0.95) - 1] / 1000, 3) if previews else None
        ),
        "archive_payload_bytes_delivered": archived,
        "archive_finished_at_ms": round(archive_finished / 1000, 3),
    }


@contextmanager
def loopback_transport(deadline_first):
    if sys.platform != "darwin":
        raise ValueError("The connected socket check uses the macOS socket options")
    with ExitStack() as stack:
        listener = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        listener.settimeout(5)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        pairs = {}
        settings = {}
        for kind, service in (("preview", VI), ("archive", BK)):
            sender = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            sender.settimeout(5)
            sender.connect(listener.getsockname())
            receiver, _ = listener.accept()
            stack.enter_context(receiver)
            receiver.settimeout(5)
            requested = service if deadline_first else BE
            sender.setsockopt(socket.SOL_SOCKET, SO_NET_SERVICE_TYPE, requested)
            if deadline_first and kind == "archive":
                sender.setsockopt(socket.SOL_SOCKET, SO_MAX_PACING_RATE, pack("=Q", LINK[-1][1]))
            observed = sender.getsockopt(socket.SOL_SOCKET, SO_NET_SERVICE_TYPE)
            rate, = unpack("=Q", sender.getsockopt(socket.SOL_SOCKET, SO_MAX_PACING_RATE, 8))
            if observed != requested or (deadline_first and kind == "archive" and rate != LINK[-1][1]):
                raise RuntimeError("Connected socket settings differed from the requested values")
            settings[kind] = {
                "service_type": observed,
                "pacing_ceiling_bytes_per_second": None if rate == (1 << 64) - 1 else rate,
            }
            pairs[kind] = (sender, receiver)

        def send_chunk(kind, size):
            sender, receiver = pairs[kind]
            byte = b"P" if kind == "preview" else b"A"
            payload = byte * size
            sender.sendall(payload)
            received = bytearray()
            while len(received) < size:
                data = receiver.recv(size - len(received))
                if not data:
                    raise RuntimeError("Loopback receiver closed before all bytes arrived")
                received.extend(data)
            if received != payload:
                raise RuntimeError("Loopback payload differed from what the sender submitted")

        yield send_chunk, settings


def run(with_loopback):
    results = {}
    for name, deadline_first in (("arrival_order", False), ("deadline_first", True)):
        if with_loopback:
            with loopback_transport(deadline_first) as (send_chunk, socket_settings):
                result = replay(deadline_first, send_chunk)
            result["loopback_socket_settings"] = socket_settings
            result["loopback_payload_checked"] = True
        else:
            result = replay(deadline_first)
        results[name] = result
    return {
        "model": {
            "frame_interval_ms": FRAME_INTERVAL_US / 1000,
            "preview_deadline_ms": PREVIEW_DEADLINE_US / 1000,
            "preview_bytes_per_frame": PREVIEW_BYTES,
            "archive_bytes_per_frame": ARCHIVE_BYTES,
            "maximum_chunk_bytes": CHUNK_BYTES,
            "link_segments": [
                {"end_ms": end / 1000 if end is not None else None, "bytes_per_second": rate}
                for end, rate in LINK
            ],
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loopback", action="store_true",
                        help="Also deliver the payload on local TCP sockets and verify their macOS service settings")
    args = parser.parse_args()
    try:
        output = run(args.loopback)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
