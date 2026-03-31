import pytest
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock
from PIL import Image

import qr_decoder_lite
from qr_decoder_lite import extract_frames, decode_frame

def test_extract_frames_success(tmp_path):
    # Mock subprocess.run to simulate successful ffmpeg execution
    # and create some mock frame files
    mock_video = "dummy.mp4"
    mock_output_dir = str(tmp_path)

    # Create mock frame files
    for i in range(1, 4):
        frame_path = os.path.join(mock_output_dir, f"frame_{i:06d}.png")
        # Just create an empty file
        with open(frame_path, "w") as f:
            f.write("mock")

    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        frames = extract_frames(mock_video, mock_output_dir, fps=5)

        assert len(frames) == 3
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-i" in args
        assert mock_video in args

def test_extract_frames_failure(tmp_path):
    # Mock subprocess.run to simulate ffmpeg failure
    mock_video = "dummy.mp4"
    mock_output_dir = str(tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error decoding video"
        mock_run.return_value = mock_result

        with pytest.raises(SystemExit) as exc:
            extract_frames(mock_video, mock_output_dir, fps=5)

        assert exc.value.code == 1

def test_decode_frame_found(tmp_path):
    # Mock zxingcpp.read_barcodes to simulate finding a QR code
    mock_frame = str(tmp_path / "mock_frame.png")

    # Create a dummy image to pass to Image.open
    img = Image.new('RGB', (100, 100), color = 'white')
    img.save(mock_frame)

    with patch('zxingcpp.read_barcodes') as mock_read:
        # Create a mock result matching zxingcpp.Result
        mock_result = MagicMock()
        mock_result.format = __import__('zxingcpp').BarcodeFormat.QRCode
        mock_result.text = "Hello QR"
        mock_read.return_value = [mock_result]

        result = decode_frame(mock_frame)
        assert result == "Hello QR"
        mock_read.assert_called_once()

def test_decode_frame_not_found(tmp_path):
    # Mock zxingcpp.read_barcodes to simulate finding nothing
    mock_frame = str(tmp_path / "mock_frame.png")

    img = Image.new('RGB', (100, 100), color = 'white')
    img.save(mock_frame)

    with patch('zxingcpp.read_barcodes') as mock_read:
        mock_read.return_value = []

        result = decode_frame(mock_frame)
        assert result is None
        mock_read.assert_called_once()
