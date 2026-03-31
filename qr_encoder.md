# QRCODE Generator
- name: qr_encoder_lite.py
- execute: python qr_encoder_lite.py < base64_log.txt
- execute: base64 log_103c.txt | python qr_encoder_lite.py
- support below args:
  * -n <split_slice_size>
    - split the base64 string into chunks of <split_slice_size>
    - generate QR code for each chunk
    - print the QR code to stdout
    - print the chunk index to stdout
    - print the total number of chunks to stdout
    - example: base64 log_103c.txt | python qr_encoder_lite.py -n 256

- support below args:
  * -d <delay_time>
    - delay <delay_time> seconds between each chunk
    - example: base64 log_103c.txt | python qr_encoder_lite.py -d 1

## tech stack
- python 3.10
- dont use any external library(such as PIL)
- dont zip the segno library as module to use, must implement the code from the scratch

## input
- base64 string

## output
- text (ASCII or UTF-8)

## requirement
- generate QR code to stdout in VT100 terminal environment, able to display in terminal, and able to scan by phone camera
- Not need to support image format
- Keep the QR code as small as possible
- Support up to version 40, auto select version based on data length
- Error correction level L

## example
- base64 log_103c.txt | python qr_encoder_lite.py

## tests
- Tests are implemented using pytest in the `tests/test_qr_encoder_lite.py` file. Run `pytest tests/test_qr_encoder_lite.py` to execute them.

## reference
- qr_encoder_lite.py