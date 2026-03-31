import pytest
import sys
import io
import os
from qr_encoder_lite import (
    _align_pos,
    _rs_encode,
    _format_info,
    _version_info,
    _select_version,
    _encode_data,
    _interleave,
    _mask_fn,
    _penalty,
    make_qr,
    _get_max_data_len
)

def test_align_pos():
    assert _align_pos(1) == []
    assert _align_pos(2) == [6, 18]
    assert _align_pos(7) == [6, 22, 38]
    assert _align_pos(40) == [6, 30, 58, 86, 114, 142, 170]

def test_rs_encode():
    # Example encoding from spec for testing
    data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
    nsym = 10
    encoded = _rs_encode(data, nsym)
    assert len(encoded) == nsym

def test_format_info():
    # Just testing it runs without errors and produces valid format info
    assert _format_info(0, 'M') == 21522
    assert _format_info(5, 'L') == 25368

def test_version_info():
    # Example version 7 version info from spec: 000111110010010100
    assert _version_info(7) == 0b000111110010010100

def test_select_version():
    assert _select_version(10, 'L') == 1
    assert _select_version(10, 'M') == 1
    # Check max version behavior
    with pytest.raises(ValueError, match="Data too long"):
        _select_version(4000, 'M', max_version=10)

def test_encode_data():
    data = [0x41, 0x42, 0x43] # "ABC"
    v = 1
    cw = _encode_data(data, v, 'L')
    assert len(cw) == 19 # Total data codewords for 1-L

def test_interleave():
    data = [0x41] * 19
    res = _interleave(data, 1, 'L')
    assert len(res) == 26 # 19 data + 7 ec

def test_mask_fn():
    assert _mask_fn(0, 0, 0) == True
    assert _mask_fn(0, 0, 1) == False
    assert _mask_fn(1, 0, 0) == True
    assert _mask_fn(1, 1, 0) == False

def test_penalty():
    # Just basic check to ensure no exception and positive value
    M = [[0]*21 for _ in range(21)]
    assert _penalty(M, 21) > 0

def test_make_qr_str():
    # Make a simple QR
    M = make_qr("Hello World", 'M')
    # Should return a 2D matrix
    assert len(M) >= 21
    assert len(M[0]) == len(M)

def test_make_qr_bytes():
    M = make_qr(b"Hello Bytes", 'L')
    assert len(M) >= 21
    assert len(M[0]) == len(M)

def test_get_max_data_len():
    # Check some max data lengths
    assert _get_max_data_len(1, 'L') == 17 # Spec for Byte mode 1-L
    assert _get_max_data_len(1, 'M') == 14 # Spec for Byte mode 1-M
