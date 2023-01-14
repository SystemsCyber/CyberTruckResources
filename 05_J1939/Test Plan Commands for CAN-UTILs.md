Test Plan Commands for CAN-UTILs (Either Beacon or Beaglebone)

1. Make the needles bounce

cangen -i -e -g 100 -I 18FEF100 -v -L 8 can1

This generates CAN message with the following switches:
 -i ignore errors
 -e use extended frames
 -g gap between messages in milliseconds
 -I identifier 18FEF100 is the cruise control vehicle speed message.
 -v verbose output, so we can see the messages
 -L length of the data field


Odometer reading. 
