import os
import sys
import io
import pytest
from PIL import Image
import zxingcpp

# Add the parent directory to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qr_encoder_img import save_qr_image, main
from qr_encoder_lite import make_qr

def test_save_qr_image(tmp_path):
    text = "Hello Verification!"
    matrix = make_qr(text.encode('utf-8'), 'M')
    filepath = str(tmp_path / "test_qr.png")
    
    # Save the image
    save_qr_image(matrix, filepath, scale=10, border=4)
    
    # Check if the file exists
    assert os.path.exists(filepath)
    
    # Verify it can be loaded with PIL and has expected properties
    img = Image.open(filepath)
    assert img.format == "PNG"
    assert img.mode == "1"
    
    # Check size calculation: matrix size S + 2 * border (4)
    S = len(matrix)
    expected_size = (S + 8) * 10
    assert img.size == (expected_size, expected_size)
    
    # Decode the generated PNG using zxingcpp to verify it's a valid QR code
    results = zxingcpp.read_barcodes(img)
    assert len(results) == 1
    assert results[0].text == text
    assert results[0].format == zxingcpp.BarcodeFormat.QRCode

def test_cli_execution(tmp_path, monkeypatch):
    # Test CLI execution via main()
    # Redirect stdout and stdin
    input_text = "CLI integration test input. CLI integration test input."
    
    monkeypatch.setattr(sys, 'stdin', io.StringIO(input_text))
    # Change current working directory to tmp_path so 'output' folder is created there
    monkeypatch.chdir(tmp_path)
    
    # Set CLI arguments
    # 56 chars split into chunks of max 25 chars -> 3 chunks
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '-n', '25', '--EC', 'L', '--scale', '5'])
    
    # Run main
    main()
    
    # Check if output directory and files were created
    output_dir = tmp_path / "output"
    assert output_dir.is_dir()
    
    files = sorted(os.listdir(output_dir))
    assert len(files) == 3
    assert files == ["qr_000001.png", "qr_000002.png", "qr_000003.png"]
    
    # Verify the first chunk's QR image decodes to the correct substring
    img1 = Image.open(output_dir / "qr_000001.png")
    results1 = zxingcpp.read_barcodes(img1)
    assert len(results1) == 1
    assert results1[0].text == input_text[:25]
    
    # Verify the last chunk's QR image decodes to the correct substring
    img3 = Image.open(output_dir / "qr_000003.png")
    results3 = zxingcpp.read_barcodes(img3)
    assert len(results3) == 1
    assert results3[0].text == input_text[50:]

def test_max_version_cli(tmp_path, monkeypatch):
    input_text = "This is a test of max-version limiting chunk size"
    # len is 50, which exceeds version 3 capacity (42 bytes for ECL M)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(input_text))
    monkeypatch.chdir(tmp_path)
    
    # Let's set --max-version to 3, EC to M, and chunk-size to 100
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '--max-version', '3', '--EC', 'M', '-n', '100'])
    
    main()
    
    # The chunk size of 100 should have been capped to 42.
    # Therefore, 50 chars of input will be split into 2 chunks (first 42, then 8)
    output_dir = tmp_path / "output"
    assert output_dir.is_dir()
    files = sorted(os.listdir(output_dir))
    assert len(files) == 2
    assert files == ["qr_000001.png", "qr_000002.png"]
    
    # Verify the first chunk's QR image decodes to the correct 42-char prefix
    img1 = Image.open(output_dir / "qr_000001.png")
    results1 = zxingcpp.read_barcodes(img1)
    assert len(results1) == 1
    assert results1[0].text == input_text[:42]

def test_invalid_max_version_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.StringIO("some data"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '--max-version', '45'])
    
    with pytest.raises(SystemExit):
        main()

