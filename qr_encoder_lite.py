#!venv/bin/python
"""qr_encoder_lite.py - Standalone QR code generator for VT100 terminals.
fElix, v0.2
Supports QR versions 1-40, EC level L/M, byte mode. No external dependencies.
Usage: echo "data" | python3 qr_encoder_lite.py
       base64 file.txt | python3 qr_encoder_lite.py
       base64 file.txt | python3 qr_encoder_lite.py -n 1100 --EC M -d 0.5
"""
import sys,os,time,select,tty,termios,hashlib

# EC parameters per version: (ec_cw_per_block, g1_count, g1_dcw, g2_count, g2_dcw)
_ECL_TAB = {
    'L': [
        None,
        (7,1,19,0,0),(10,1,34,0,0),(15,1,55,0,0),(20,1,80,0,0),(26,1,108,0,0),
        (18,2,68,0,0),(20,2,78,0,0),(24,2,97,0,0),(30,2,116,0,0),(18,2,68,2,69),
        (20,4,81,0,0),(24,2,92,2,93),(26,4,107,0,0),(30,3,115,1,116),(22,5,87,1,88),
        (24,5,98,1,99),(28,1,107,5,108),(30,5,120,1,121),(28,3,113,4,114),(28,3,107,5,108),
        (28,4,116,4,117),(28,2,111,7,112),(30,4,121,5,122),(30,6,117,4,118),(26,8,106,4,107),
        (28,10,114,2,115),(30,8,122,4,123),(30,3,117,10,118),(30,7,116,7,117),(30,5,115,10,116),
        (30,13,115,3,116),(30,17,115,0,0),(30,17,115,1,116),(30,13,115,6,116),(30,12,121,7,122),
        (30,6,121,14,122),(30,17,122,4,123),(30,4,122,18,123),(30,20,117,4,118),(30,19,118,6,119),
    ],
    'M': [
        None,
        (10,1,16,0,0),(16,1,28,0,0),(26,1,44,0,0),(18,2,32,0,0),(24,2,43,0,0),
        (16,4,27,0,0),(18,4,31,0,0),(22,2,38,2,39),(22,3,36,2,37),(26,4,43,1,44),
        (30,1,50,4,51),(22,6,36,2,37),(22,8,37,1,38),(24,4,40,5,41),(24,5,41,5,42),
        (28,7,45,3,46),(28,10,46,1,47),(26,9,43,4,44),(26,3,44,11,45),(26,3,41,13,42),
        (26,17,42,0,0),(28,17,46,0,0),(28,4,47,14,48),(28,6,45,14,46),(28,8,47,13,48),
        (28,19,46,4,47),(28,22,45,3,46),(28,3,45,23,46),(28,21,45,7,46),(28,19,47,10,48),
        (28,2,46,29,47),(28,10,46,23,47),(28,14,46,21,47),(28,14,46,23,47),(28,12,47,26,48),
        (28,6,47,34,48),(28,29,46,14,47),(28,13,46,32,47),(28,40,47,7,48),(28,18,47,31,48),
    ]
}

def _align_pos(v):
    if v < 2: return []
    n = v // 7 + 2
    last = 4 * v + 10
    if n == 2: return [6, last]
    step = -(-(last - 6) // (n - 1))
    if step % 2: step += 1
    pos = [last]
    for _ in range(n - 2):
        pos.insert(0, pos[0] - step)
    pos.insert(0, 6)
    return pos

def _rs_encode(data, nsym):
    EXP = [1] * 512; LOG = [0] * 256; x = 1
    for i in range(255):
        EXP[i] = x; LOG[x] = i
        x <<= 1
        if x & 256: x ^= 0x11d
    for i in range(255, 512): EXP[i] = EXP[i - 255]
    g = [1]
    for i in range(nsym):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            if c:
                ng[j] ^= EXP[LOG[c]]
                ng[j + 1] ^= EXP[LOG[c] + i]
        g = ng
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef:
            for j in range(len(g)):
                res[i + j] ^= EXP[LOG[g[j]] + LOG[coef]] if g[j] else 0
    return res[-nsym:]

def _format_info(mask, ec_level='L'):
    ec_bits = 1 if ec_level == 'L' else 0
    data = (ec_bits << 3) | mask
    d = data << 10
    for i in range(14, 9, -1):
        if d & (1 << i): d ^= 0x537 << (i - 10)
    return (data << 10 | d) ^ 0x5412

def _version_info(v):
    d = v << 12
    for i in range(17, 11, -1):
        if d & (1 << i): d ^= 0x1F25 << (i - 12)
    return (v << 12) | d

def _select_version(data_len, ec_level, max_v):
    for v in range(1, max_v + 1):
        ec, g1n, g1d, g2n, g2d = _ECL_TAB[ec_level][v]
        total_dcw = g1n * g1d + g2n * g2d
        cc = 8 if v <= 9 else 16
        if data_len <= (total_dcw * 8 - 4 - cc) // 8:
            return v
    raise ValueError(f"Data too long ({data_len} bytes) for version {max_v}")

def _encode_data(data, v, ec_level):
    ec, g1n, g1d, g2n, g2d = _ECL_TAB[ec_level][v]
    total_dcw = g1n * g1d + g2n * g2d
    cc = 8 if v <= 9 else 16
    bits = [0, 1, 0, 0]
    n = len(data)
    for i in range(cc - 1, -1, -1): bits.append((n >> i) & 1)
    for b in data:
        for i in range(7, -1, -1): bits.append((b >> i) & 1)
    for _ in range(min(4, total_dcw * 8 - len(bits))): bits.append(0)
    pad_bits = (8 - len(bits) % 8)  # 1-8 bits to next byte boundary
    bits.extend([0] * min(pad_bits, total_dcw * 8 - len(bits)))
    cw = [int(''.join(str(b) for b in bits[i:i+8]), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]; pi = 0
    while len(cw) < total_dcw: cw.append(pad[pi]); pi ^= 1
    return cw

def _interleave(data_cw, v, ec_level):
    ec_per, g1n, g1d, g2n, g2d = _ECL_TAB[ec_level][v]
    blocks = []; pos = 0
    for _ in range(g1n): blocks.append(data_cw[pos:pos+g1d]); pos += g1d
    for _ in range(g2n): blocks.append(data_cw[pos:pos+g2d]); pos += g2d
    ec_blocks = [_rs_encode(blk, ec_per) for blk in blocks]
    result = []
    max_d = max(len(b) for b in blocks)
    for i in range(max_d):
        for b in blocks:
            if i < len(b): result.append(b[i])
    for i in range(ec_per):
        for e in ec_blocks: result.append(e[i])
    return result

def _mask_fn(mask, r, c):
    if mask == 0: return (r + c) % 2 == 0
    if mask == 1: return r % 2 == 0
    if mask == 2: return c % 3 == 0
    if mask == 3: return (r + c) % 3 == 0
    if mask == 4: return (r // 2 + c // 3) % 2 == 0
    if mask == 5: return (r * c) % 2 + (r * c) % 3 == 0
    if mask == 6: return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0

def _penalty(M, S):
    score = 0
    # Rule 1: runs of 5+ same color in rows and columns
    for i in range(S):
        for horizontal in (True, False):
            run = 1
            for j in range(1, S):
                a = M[i][j] if horizontal else M[j][i]
                b = M[i][j-1] if horizontal else M[j-1][i]
                if a == b:
                    run += 1
                else:
                    if run >= 5: score += 3 + run - 5
                    run = 1
            if run >= 5: score += 3 + run - 5
    # Rule 2: 2x2 blocks
    for r in range(S - 1):
        for c in range(S - 1):
            v = M[r][c]
            if v == M[r][c+1] == M[r+1][c] == M[r+1][c+1]:
                score += 3
    # Rule 3: finder-like patterns
    p1 = [1,0,1,1,1,0,1,0,0,0,0]
    p2 = [0,0,0,0,1,0,1,1,1,0,1]
    for i in range(S):
        for j in range(S - 10):
            row = [M[i][j+k] for k in range(11)]
            col = [M[j+k][i] for k in range(11)]
            if row == p1 or row == p2: score += 40
            if col == p1 or col == p2: score += 40
    # Rule 4: dark module ratio
    dark = sum(M[r][c] for r in range(S) for c in range(S))
    pct = dark * 100 // (S * S)
    prev5 = (pct // 5) * 5
    next5 = prev5 + 5
    score += min(abs(prev5 - 50), abs(next5 - 50)) // 5 * 10
    return score

def make_qr(data, ec_level='L', max_v=20):
    if isinstance(data, str): data = data.encode('utf-8')
    data = list(data)
    v = _select_version(len(data), ec_level, max_v)
    S = 4 * v + 17

    data_cw = _encode_data(data, v, ec_level)
    codewords = _interleave(data_cw, v, ec_level)
    bits = []
    for b in codewords:
        for i in range(7, -1, -1): bits.append((b >> i) & 1)
    # Remainder bits per ISO 18004 Section 7.6
    rem = 7 if v in (2,3,4,5,6) else 4 if 21 <= v <= 27 else 3 if 14 <= v <= 34 else 0
    bits.extend([0] * rem)

    # Build function pattern map: True = function cell
    F = [[False] * S for _ in range(S)]
    M = [[0] * S for _ in range(S)]

    def _set(r, c, val):
        if 0 <= r < S and 0 <= c < S:
            M[r][c] = val; F[r][c] = True

    def _rect(r, c, w, h, val):
        for i in range(h):
            for j in range(w): _set(r + i, c + j, val)

    def _finder(r, c):
        _rect(r - 1, c - 1, 9, 9, 0)
        _rect(r, c, 7, 7, 1)
        _rect(r + 1, c + 1, 5, 5, 0)
        _rect(r + 2, c + 2, 3, 3, 1)

    _finder(0, 0); _finder(0, S - 7); _finder(S - 7, 0)

    # Alignment patterns
    centers = _align_pos(v)
    for ar in centers:
        for ac in centers:
            if not F[ar][ac]:
                _rect(ar - 2, ac - 2, 5, 5, 1)
                _rect(ar - 1, ac - 1, 3, 3, 0)
                _set(ar, ac, 1)

    # Timing patterns
    for i in range(S):
        if not F[6][i]: _set(6, i, int(i % 2 == 0))
        if not F[i][6]: _set(i, 6, int(i % 2 == 0))

    # Dark module
    _set(4 * v + 9, 8, 1)

    # Version info (V7+)
    if v >= 7:
        vi = _version_info(v)
        for i in range(6):
            for j in range(3):
                bit = (vi >> (i * 3 + j)) & 1
                _set(i, S - 11 + j, bit)
                _set(S - 11 + j, i, bit)

    # Reserve format info areas as function cells
    for i in range(9):
        F[8][i] = True; F[i][8] = True
    for i in range(8):
        F[S - 1 - i][8] = True; F[8][S - 8 + i] = True

    # Place data bits
    data_cells = []  # list of (r, c) for data cells in placement order
    idx = 0; dr = -1; r = S - 1; c = S - 1
    while c > 0:
        if c == 6: c -= 1
        for _ in range(S):
            for j in [0, 1]:
                cc = c - j
                if not F[r][cc]:
                    data_cells.append((r, cc))
                    M[r][cc] = bits[idx] if idx < len(bits) else 0
                    idx += 1
            r += dr
        r -= dr; dr = -dr; c -= 2

    # Try all 8 masks, pick best
    best_score = None; best_mask = 0; best_matrix = None
    for mask in range(8):
        # Copy matrix and apply mask to data cells
        T = [row[:] for row in M]
        for (r, c) in data_cells:
            if _mask_fn(mask, r, c):
                T[r][c] ^= 1
        # Write format info (ISO 18004 Section 7.9.1)
        fi = _format_info(mask, ec_level)
        voff = hoff = 0
        for i in range(8):
            vbit = (fi >> i) & 1          # LSB first
            hbit = (fi >> (14 - i)) & 1   # MSB first
            if i == 6:  # skip timing pattern
                voff = 1; hoff = 1
            T[i + voff][8] = vbit         # vertical, upper-left
            T[8][i + hoff] = hbit         # horizontal, upper-left
            T[8][S - 1 - i] = vbit        # horizontal, upper-right
            T[S - 1 - i][8] = hbit        # vertical, bottom-left
        T[S - 8][8] = 1  # dark module (always dark)

        sc = _penalty(T, S)
        if best_score is None or sc < best_score:
            best_score = sc; best_mask = mask; best_matrix = T

    return best_matrix

def terminal(M):
    S = len(M)
    E = [False] * (S + 8)
    R = [E] * 4
    for row in M:
        R.append([False] * 4 + [bool(x) for x in row] + [False] * 4)
    R += [E] * 4
    lines = []
    for y in range(0, len(R), 2):
        l = ""
        for x in range(len(R[0])):
            t = not R[y][x]
            b = not (R[y + 1][x] if y + 1 < len(R) else False)
            if t and b: l += "\u2588"
            elif t: l += "\u2580"
            elif b: l += "\u2584"
            else: l += " "
        lines.append(l)
    print('\n'.join(lines))

def _wait(duration):
    """Sleep for `duration` seconds, but skip immediately if user presses a key."""
    try:
        tty_f = open('/dev/tty', 'r')
    except OSError:
        time.sleep(duration)
        return
    fd = tty_f.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        r, _, _ = select.select([tty_f], [], [], duration)
        if r:
            tty_f.read(1)  # consume the keypress
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        tty_f.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate QR codes from stdin')
    parser.add_argument('-n', '--chunk-size', type=int, default=1000, metavar='SIZE',
                        help='Split input into chunks of SIZE characters')
    parser.add_argument('-d', '--delay', type=float, default=0, metavar='DELAY',
                        help='Delay <DELAY> seconds between each chunk, default 0')
    parser.add_argument('--EC', choices=['L', 'M'], default='M',
                        help='Error correction level (L or M), default M')
    parser.add_argument('--version', type=int, default=20, metavar='VER',
                        help='Maximum QR version (1-40) to use, default 20. Data must fit within this version.')

    args = parser.parse_args()
    data = sys.stdin.read().strip()
    if not data:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    if args.delay > 0:
       os.system('clear')
       print(f"\nDetected player mode, going to start in 3 seconds\n") 
       _wait(3)

    if args.chunk_size > 0:
        chunks = [data[i:i+args.chunk_size] for i in range(0, len(data), args.chunk_size)]
        total = len(chunks)
        for idx, chunk in enumerate(chunks, 1):
            if args.delay > 0:
                os.system('clear')
            cbytes = chunk.encode('utf-8')
            v = _select_version(len(cbytes), args.EC, args.version)
            md5 = hashlib.md5(cbytes).hexdigest()
            print(f"\nchunk {idx}/{total} (v{v}, md5: {md5})\n")
            terminal(make_qr(cbytes, args.EC, args.version))
            if args.delay > 0:
                _wait(args.delay)
    else:
        cbytes = data.encode('utf-8')
        v = _select_version(len(cbytes), args.EC, args.version)
        md5 = hashlib.md5(cbytes).hexdigest()
        print(f"\nchunk 1/1 (v{v}, md5: {md5})\n")
        terminal(make_qr(cbytes, args.EC, args.version))

