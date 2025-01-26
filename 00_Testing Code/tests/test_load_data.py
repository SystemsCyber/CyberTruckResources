
from loadDatabase_j1939 import * #Import the file with the function to test
import os

def test_overwrite_db(faker):
    # Define the random file names
    db_file = faker.file_name()
    candump_file = faker.file_name()
    
    timestamp = 1724771346.025320
    channel = faker.word()
    can_id_int = faker.random_int(min=0, max=0x1FFFFFFF)
    can_id = f"{can_id_int:08X}"
    can_data = "180194018502FFFF"
    can_dump_data = f"({timestamp}) {channel} {can_id}#{can_data}"
    pgn, sa = parse_j1939_id(can_id)
    
    with open(candump_file,'w') as f:
        f.write(can_dump_data)
    #Confirm the new file was created
    assert os.path.exists(candump_file)

    #Call the function to test
    create_database(db_file)
    #Confirm the new file was created
    assert os.path.exists(db_file)

    parse_and_store_candump(candump_file, db_file)
    
    #Check to see if the data was written as desired
    
    #Reads and returns the first line of the database.
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candata LIMIT 1")
    first_line = cursor.fetchone()
    conn.close()
    print(first_line)

    #Check Source Address
    assert first_line[0] == sa 
    assert isinstance(first_line[0],int)
    # Check Parameter Group Number
    assert first_line[1] == pgn
    assert isinstance(first_line[1],int)
    # Check CAN ID
    assert first_line[2] == can_id
    assert isinstance(first_line[2],str)
    # Check timestamp
    assert first_line[3] == timestamp
    assert isinstance(first_line[3],float)
    # check Data
    assert first_line[4] == can_data
    assert isinstance(first_line[4],str)
    #What if we wanted bytes?
    #assert isinstance(first_line[4],bytes)
    

    #clean up after the test is completed
    os.remove(candump_file)
    os.remove(db_file)
    


    