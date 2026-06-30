ID=0; 
for mov in input_mov/*.MOV; do 
	ID=$(($ID + 1));
 	echo $ID; 
	echo $mov; 
        if [[ $ID -gt 11 ]]; then
          venv/bin/python qr_decoder_lite.py $mov --max-chunk 103   # --skip-decod
          cp tmp_decode.base64 output_mov/split.$ID; 
	fi
done; 

