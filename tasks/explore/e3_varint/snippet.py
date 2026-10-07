def decode_stream(buf: bytes, *, signed: bool = False, max_bytes: int = 10):
    pos, n = 0, len(buf)
    while pos < n:
        result = shift = 0
        start = pos
        while True:
            if pos >= n:
                raise ValueError(f"truncated varint at offset {start}")
            b = buf[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
            if pos - start >= max_bytes:
                raise ValueError(f"varint too long at offset {start}")
        if signed:
            result = (result >> 1) ^ -(result & 1)
        yield result
