import asyncio
import socket

import requests


def fetch_all(urls: list[str], **kwargs) -> list[bytes]:
    out = []
    for url in urls:
        out.append(requests.get(url, **kwargs).content)
    return out


def ping_smtp(host: str) -> bool:
    sock = socket.create_connection((host, 25))
    try:
        return sock.recv(3) == b"220"
    finally:
        sock.close()


def ping_redis(host: str) -> bool:
    sock = socket.create_connection((host, 6379), timeout=1.5)
    try:
        sock.sendall(b"PING\r\n")
        return sock.recv(7) == b"+PONG\r\n"
    finally:
        sock.close()


async def read_banner(host: str, port: int) -> bytes:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
    try:
        return await reader.readline()
    finally:
        writer.close()


async def post_metrics(host: str, payload: bytes) -> None:
    reader, writer = await asyncio.open_connection(host, 8125)
    writer.write(payload)
    await writer.drain()
    writer.close()
