# QRCODE Decoder
- name: qr_decoder_lite.py <video_filename>
- execute: python qr_decoder_lite.py test.mp4
- python qr_decoder_lite.py test.mp4 > xxx.b64
## tech stack
- python 3.10
- use venv to manage dependencies
- use Pillow and zxing-cpp (pip install Pillow zxing-cpp)
- use ffmpeg (system) for video frame extraction

## input
- video file

## output
- text (ASCII, base64 string)

## requirement
- decode QR code from video file

## example
- python qr_decoder_lite.py test.mp4

## tests
- Tests are implemented using pytest in the `tests/test_qr_decoder_lite.py` file. Run `pytest tests/test_qr_decoder_lite.py` to execute them.

## reference





