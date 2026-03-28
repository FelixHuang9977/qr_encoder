clear;clear
dd if=/dev/urandom of=target-file bs=1 count=2000

slice_size=1100

base64 target-file | split -b $slice_size
base64 target-file > full_base64

base64 target-file | python qr_encoder_lite.py --EC M -n $slice_size "$@"

md5sum target-file
