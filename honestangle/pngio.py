"""Pure-stdlib PNG reading and writing for RGB8 and RGBA8, non-interlaced.

HonestAngle deliberately keeps its core dependency free: provenance hashing
must be reproducible on a bare Python install. Interlaced PNGs and non-8-bit
depths are rejected loudly rather than misread.
"""
import struct
import zlib


class PngError(ValueError):
    pass


_SIG = b"\x89PNG\r\n\x1a\n"


def _read_chunks(data):
    if data[:8] != _SIG:
        raise PngError("not a PNG file")
    pos = 8
    chunks = []
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise PngError("truncated chunk")
        chunks.append((ctype, body))
        pos += 12 + length
        if ctype == b"IEND":
            break
    if pos != len(data):
        raise PngError("trailing bytes after IEND")
    return chunks


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, width, height, channels):
    stride = width * channels
    out = bytearray(stride * height)
    prev = memoryview(out)[:0]
    pos = 0
    for y in range(height):
        ft = raw[pos]
        row = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft == 0:
            pass
        elif ft == 1:  # Sub
            for i in range(channels, stride):
                row[i] = (row[i] + row[i - channels]) & 0xFF
        elif ft == 2:  # Up
            if y:
                pv = memoryview(out)[(y - 1) * stride:y * stride]
                for i in range(stride):
                    row[i] = (row[i] + pv[i]) & 0xFF
        elif ft == 3:  # Average
            pv = memoryview(out)[(y - 1) * stride:y * stride] if y else bytes(stride)
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                row[i] = (row[i] + ((left + pv[i]) >> 1)) & 0xFF
        elif ft == 4:  # Paeth
            pv = memoryview(out)[(y - 1) * stride:y * stride] if y else bytes(stride)
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                ul = pv[i - channels] if (y and i >= channels) else 0
                row[i] = (row[i] + _paeth(left, pv[i], ul)) & 0xFF
        else:
            raise PngError("unknown filter type %d" % ft)
        out[y * stride:(y + 1) * stride] = row
        prev = row
    return bytes(out)


def read_png(path):
    """Return (width, height, channels, pixels) for RGB8 (3) or RGBA8 (4)."""
    with open(path, "rb") as f:
        data = f.read()
    chunks = _read_chunks(data)
    ihdr = None
    idat = bytearray()
    for ctype, body in chunks:
        if ctype == b"IHDR":
            ihdr = body
        elif ctype == b"IDAT":
            idat.extend(body)
    if ihdr is None or len(ihdr) != 13:
        raise PngError("bad IHDR")
    width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if depth != 8:
        raise PngError("only 8-bit depth supported, got %d" % depth)
    if color not in (2, 6):
        raise PngError("only RGB8 (2) and RGBA8 (6) supported, got color type %d" % color)
    if comp != 0 or filt != 0:
        raise PngError("unsupported compression/filter method")
    if interlace != 0:
        raise PngError("interlaced PNGs are not supported")
    channels = 3 if color == 2 else 4
    raw = zlib.decompress(bytes(idat))
    need = height * (1 + width * channels)
    if len(raw) != need:
        raise PngError("unexpected decompressed size")
    pixels = _unfilter(raw, width, height, channels)
    return width, height, channels, pixels


def _filter_none(rows):
    out = bytearray()
    for row in rows:
        out.append(0)
        out.extend(row)
    return bytes(out)


def write_png_file(path, width, height, channels, pixels):
    if channels not in (3, 4):
        raise PngError("write_png_file supports 3 or 4 channels")
    stride = width * channels
    if len(pixels) != stride * height:
        raise PngError("pixel buffer size mismatch")
    parts = [_SIG]

    def chunk(ctype, body):
        return struct.pack(">I", len(body)) + ctype + body + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)

    parts.append(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)))
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(memoryview(pixels)[y * stride:(y + 1) * stride])
    parts.append(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
    parts.append(chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(b"".join(parts))
