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

def test_old_images_are_deleted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create some dummy stale qr_*.png files
    stale_file = output_dir / "qr_999999.png"
    stale_file.write_text("dummy content")
    assert stale_file.exists()
    
    # Run main with a single chunk input
    monkeypatch.setattr(sys, 'stdin', io.StringIO("Short test input"))
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '-n', '100'])
    main()
    
    # Verify that the stale file was deleted, and the new chunk file was created
    assert not stale_file.exists()
    assert (output_dir / "qr_000001.png").exists()

def test_save_qr_image_with_label(tmp_path):
    text = "Label Test!"
    matrix = make_qr(text.encode('utf-8'), 'M')
    filepath_no_label = str(tmp_path / "qr_no_label.png")
    filepath_label = str(tmp_path / "qr_label.png")
    
    # Save standard
    save_qr_image(matrix, filepath_no_label, scale=10, border=4)
    # Save with label
    label_str = "Test Label - Chunk 1"
    save_qr_image(matrix, filepath_label, scale=10, border=4, label=label_str)
    
    img_no_label = Image.open(filepath_no_label)
    img_label = Image.open(filepath_label)
    
    # Labeled image should be taller by 30 pixels (since scale=10, font_size=15, extra_height=30)
    assert img_label.size[0] == img_no_label.size[0]
    assert img_label.size[1] == img_no_label.size[1] + 30
    
    # Decode using zxingcpp to make sure the label doesn't break the QR reader
    results = zxingcpp.read_barcodes(img_label)
    assert len(results) == 1
    assert results[0].text == text

def test_cli_label_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    
    monkeypatch.setattr(sys, 'stdin', io.StringIO("Demo data for label"))
    # Pass --label auto
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '-n', '100', '--label'])
    main()
    
    img = Image.open(output_dir / "qr_000001.png")
    # It should have extra height since --label (defaults to auto -> filename) is used
    # Matrix size for v2 is S=25, with border=4, new_size=33. Scaled by 10 = 330. Plus 30 extra height = 360.
    assert img.size == (330, 360)

def test_cli_default_datetime_label(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    
    monkeypatch.setattr(sys, 'stdin', io.StringIO("Demo data for label"))
    # Do NOT pass --label at all
    monkeypatch.setattr(sys, 'argv', ['qr_encoder_img.py', '-n', '100'])
    main()
    
    img = Image.open(output_dir / "qr_000001.png")
    # Matrix size for v2 is S=25, with border=4, new_size=33. Scaled by 10 = 330. Plus 30 extra height = 360.
    assert img.size == (330, 360)
