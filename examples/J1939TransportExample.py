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
    with open(filename,'r') as f:
        for line in f:
            # We knew this data file was from Linux SocketCAN using candump.
            j1939_frame = parse_candump_line(line)
            # Add the additional results from parsing the id
            j1939_frame.update(parseJ1939id(j1939_frame['id']))
            transport_data = parseJ1939(j1939_frame)
            if transport_data is not None:
                j1939_frame.update(transport_data)
            # PGN for electronic engine control 1 messsage
            if (j1939_frame['pgn'] == PGN_EEC1 and 
                j1939_frame["source_address"] == ENGINE_SA): 
                # Unpack the engine speed data in big endian format and 
                # convert to engineering values
                rpm = (struct.unpack('<H',j1939_frame['data'][3:5])[0]
                         * SPN190_SCALE + SPN190_OFFSET)
                spn190_values.append(rpm)
                # Include the timestamp for time series data
                spn190_times.append(j1939_frame['timestamp'])
            
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

TP_messages = {}
def parseJ1939(j1939_message):
    pgn = j1939_message['pgn']
    sa = j1939_message['source_address']
    da = j1939_message['destination_address']
    j1939_data_frame = j1939_message['data']
    if pgn == 0xEC00: #Transport Protocol Connection Management (TP.CM)
        control_byte = j1939_data_frame[0]
        if control_byte == 16: #Connection Mode Request to Send (TP.CM_RTS): Destination Specific
            message_size = struct.unpack('<H',j1939_data_frame[1:3])[0]
            total_packets = j1939_data_frame[3]
            num_packets_to_send = j1939_data_frame[4]
            new_pgn = j1939_data_frame[5] | (j1939_data_frame[6] << 8) | (j1939_data_frame[7] << 16)
            TP_messages[(sa,da)] = J1939TransportMessage(
                                            new_pgn,
                                            sa,
                                            da,
                                            total_packets,
                                            message_size)
            num_can_be_sent = min(num_packets_to_send,total_packets)

            # #Craft a CAN Frame to be the CTS message using RP1210
            # response_message  = b'\x01' #extended frame
            # response_message += b'\x18' #priority
            # response_message += b'\xEC' #PGN
            # response_message += struct.pack('B',sa) #DA
            # response_message += struct.pack('B',da) #SA of 
            # response_message += b'\x11' #TP.CM_CTS control byte
            # response_message += struct.pack('B',num_can_be_sent) #Number of packets that can be sent
            # response_message += b'\x01' #Next packet number
            # response_message += b'\xFF\xFF' # Reserved
            # response_message += struct.pack("<L",new_pgn)[:3]
            # send_message(response_message)

        elif control_byte == 17: #Connection Mode Clear to Send (TP.CM_CTS):
            logger.debug("Received clear to send message.")
            TP_messages[(sa,da)].num_packets_to_send = j1939_data_frame[1]
            TP_messages[(sa,da)].next_packet = j1939_data_frame[2] #len(self.TP_messages[(sa,da)].message) + 1
            #j1939_data_frame[3] == 0xFF
            #j1939_data_frame[4] == 0xFF
            TP_messages[(sa,da)].cts_pgn = j1939_data_frame[5] | (j1939_data_frame[6] << 8) | (j1939_data_frame[7] << 16)
            TP_messages[(sa,da)].CTS = True
        elif control_byte == 19:
            logger.debug("Received End of Message Acknowledgement")
        elif control_byte == 255:
            logger.debug("Received Connection Abort")
            # Reset the message list
            try:
                TP_messages[(sa,da)].message = []
            except KeyError:
                pass
        elif control_byte == 32:
            print("Received Broadcast Announce Message from {:02X} to {:02X}".format(sa,da))  
            message_size = struct.unpack('<H',j1939_data_frame[1:3])[0]
            total_packets = j1939_data_frame[3]
            new_pgn = j1939_data_frame[5] | (j1939_data_frame[6] << 8) | (j1939_data_frame[7] << 16)
            ##da = 0xFF
            if (sa,da) in TP_messages: #Session hasn't been completed yet
                print("Found an TP.CM message before messages completed.")
            #go with the latest TP.CM command.
            TP_messages[(sa,da)] = J1939TransportMessage(
                                            new_pgn,
                                            sa,
                                            da,
                                            total_packets,
                                            message_size)   
        return None
    elif pgn == 0xEB00: #Transport Protocol Data Transfer (TP.DT)
        if (sa,da) not in TP_messages: #Need to setup a session first.
            return None
        if TP_messages[(sa,da)].add_frame(j1939_data_frame):
            #returns True if all the messages have arrived
            (pgn, sa, da, return_message) = TP_messages[(sa,da)].get_message()
            print("Found Transport Layer Message from {:02X} to {:02X}\n{}".format(sa,da,return_message))
            #Delete the entry for the complete message
            TP_messages.pop((sa,da))

            return {'source_address': sa,
                    'destination_address': da,
                    'pgn': pgn,
                    'dlc': len(return_message),
                    'data': return_message}
        else:
            return None
    else:
        # It's a normal 8-byte frame, not transport layer
        return None

class J1939TransportMessage():
    def __init__(self,new_pgn,sa,da,total_packets,message_size):
        self.pgn = new_pgn
        self.sa = sa
        self.da = da
        self.message = {}
        self.total_packets = total_packets
        self.message_size = message_size
        self.num_packets_to_send = 0
        self.next_packet = 1
        self.cts_pgn = new_pgn 
        self.ack_pgn = new_pgn
        self.CTS = False
        self.RTS = False
        self.ACK = False

    def add_frame(self,can_frame):
        sequence_num = can_frame[0]
        self.message[sequence_num] = can_frame[1:]
        if len(self.message) == self.total_packets:
            # The message is complete
            return True
        else:
            return False

    def get_message(self):
        if len(self.message) == self.total_packets:
            return_message = b''
            for i in range(1, self.total_packets+1):
                try:
                    return_message += self.message[i]
                except KeyError:
                    print(("Transport Layer Sequence number missing."))
                    return None
            self.message = []
            return (self.pgn, self.sa, self.da, return_message[:self.message_size])
        else:
            return None

if __name__ == '__main__':
    main()