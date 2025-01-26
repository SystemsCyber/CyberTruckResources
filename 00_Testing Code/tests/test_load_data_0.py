
from loadDatabase_0 import * #Import the file with the function to test
import os

def test_overwrite_db(faker):
    # Define the database file name
    db_file = "can_data.db"
    candump_file = faker.file_name()
    can_dump_data = "(1553794338.000001) can0 18FEF200#180194018502FFFF"
    with open(candump_file,'w') as f:
        f.write(can_dump_data)
    #Confirm the new file was created
    assert os.path.exists(candump_file)

    #Call the function to test
    create_database(db_file)
    #Confirm the new file was created
    assert os.path.exists(db_file)

    parse_and_store_candump(db_file, candump_file)
    
    
    #Check to see if the data was written as desired

    #Reads and returns the first line of the database.
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candata LIMIT 1")
    first_line = cursor.fetchone()
    conn.close()
    print(first_line)
    assert first_line in can_dump_data

    #clean up after the test is completed
    os.remove(candump_file)
    os.remove(db_file)
    


    