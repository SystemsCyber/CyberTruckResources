import json
import struct

CANDUMP_TIMESTAMP_ADDR = 0
CANDUMP_CHANNEL_ADDR   = 1
CANDUMP_ID_ADDR        = 2
CANDUMP_DLC_ADDR       = 3
DATA_START_ADDR        = 4

def main():
	with open('KWTruck.txt','r') as f:
		for line in f:
			data = line.strip().split()
			print(parse_candump_line(data))


def parse_candump_line(data):
	# can_dump formats use parenthese to wrap the floating
	# point timestamp. We just want the numbers so use [1:-1] to slice
	time_stamp = float(data[CANDUMP_TIMESTAMP_ADDR][1:-1])
	# physical CAN channel
	channel = data[CANDUMP_CHANNEL_ADDR]
	# determine the can arbitration identifier as an integer
	can_id = int(data[CANDUMP_ID_ADDR],16)
	# Data length code is a single byte wrapped in []
	dlc = int(data[CANDUMP_DLC_ADDR][1])
	# Build the data field as a byte array
	data_bytes = b''
	for byte_string in data[DATA_START_ADDR:]:
		data_bytes += struct.pack('B',int(byte_string,16))
	#assert dlc == len(data_bytes)
	can_frame = {'id':can_id,
				 'dlc':dlc,
				 'data':data_bytes,
				 'timestamp':time_stamp,
				 'channel':channel}
	return can_frame

if __name__ == '__main__':
	main()

