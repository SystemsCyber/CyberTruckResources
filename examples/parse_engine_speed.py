#!/usr/bin/env python3
import struct
import matplotlib.pyplot as plt

PRIORITY_MASK       = 0x1C000000
PDU_FORMAT_MASK     = 0x00FF0000
PDU_SPECIFIC_MASK   = 0x0000FF00 
SOURCE_ADDRESS_MASK = 0x000000FF 
DATA_PAGE_MASK      = 0x01000000 
EXT_DATA_PAGE_MASK  = 0x02000000 
PDU1_PGN_MASK       = 0x03FF0000 
PDU2_PGN_MASK       = 0x03FFFF00

PRIORITY_OFFSET    = 26 
PDU_FORMAT_OFFSET  = 16 
DA_OFFSET          = 8 
PGN_OFFSET         = 8
PDU2_THRESHOLD     = 240

GLOBAL_SOURCE_ADDR = 0xFF
ENGINE_SA          = 0

CANDUMP_TIMESTAMP_ADDR = 0
CANDUMP_CHANNEL_ADDR   = 1
CANDUMP_ID_ADDR        = 2
CANDUMP_DLC_ADDR       = 3
DATA_START_ADDR        = 4

PGN_EEC1 = 61444

SPN190_SCALE = 0.125 #RPM/bit
SPN190_OFFSET = 0

def main():
    spn190_times = []
    spn190_values = []
    filename = 'KWTruck.txt'
    sa_count={}
    with open(filename,'r') as f:
        for line in f:
            # We knew this data file was from Linux SocketCAN using candump.
            j1939_frame = parse_candump_line(line)
            # Add the additional results from parsing the id
            j1939_frame.update(parseJ1939id(j1939_frame['id']))
            # PGN for electronic engine control 1 messsage
            try:
                sa_count[j1939_frame["source_address"]]+=1
            except KeyError:    
                sa_count[j1939_frame["source_address"]]=1
            if (j1939_frame['pgn'] == PGN_EEC1 and 
                j1939_frame["source_address"] == ENGINE_SA): 
                # Unpack the engine speed data in big endian format and 
                # convert to engineering values
                rpm = (struct.unpack('<H',j1939_frame['data'][3:5])[0]
                         * SPN190_SCALE + SPN190_OFFSET)
                spn190_values.append(rpm)
                # Include the timestamp for time series data
                spn190_times.append(j1939_frame['timestamp'])
    print(sa_count)        
    #Plot the engine speed  
    plt.plot(spn190_times,spn190_values,'-',label="Engine RPM")
    plt.xlabel("Time (sec.)")
    plt.ylabel("Engine Speed (RPM)")
    plt.title("Engine Speed for {}".format(filename))
    plt.grid()
    plt.legend()
    #plt.show()
    plt.savefig('EngineSpeedGraphFrom{}.pdf'.format(filename))

def parseJ1939id(id):
    sa = id & SOURCE_ADDRESS_MASK
    priority = (id & PRIORITY_MASK) >> PRIORITY_OFFSET
    pf = (id & PDU_FORMAT_MASK) >> PDU_FORMAT_OFFSET
    if (pf < PDU2_THRESHOLD):  # See SAE J1939-21
        # PDU 1 format uses values lower than 240
        da = (id & PDU_SPECIFIC_MASK) >> DA_OFFSET
        pgn = (id & PDU1_PGN_MASK) >> PGN_OFFSET
    else:         # PDU 2 format
        da = GLOBAL_SOURCE_ADDR
        pgn = (id & PDU2_PGN_MASK) >> PGN_OFFSET
    return {'source_address': sa,
            'priority': priority,
            'destination_address': da,
            'pgn': pgn}

def parse_candump_line(line):
    # Strip the newline characters and white space off the ends
    # then split the string into a list based on whitespace. 
    data = line.strip().split()         
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
        # Convert text into a single byte
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

