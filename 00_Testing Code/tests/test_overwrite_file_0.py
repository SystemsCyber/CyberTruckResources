
from loadDatabase_0 import * #Import the file with the function to test
import os

def test_read_data_db(faker):
    # Define the database file name
    db_file = faker.file_name()

    #Call the function to create the db
    with open(db_file,'w') as f:
        f.write("This is a test file, not a db file.")

    #Confirm the new file was created
    assert os.path.exists(db_file)

    #Call the function to test
    create_database(db_file)

    #clean up after the test is completed
    os.remove(db_file)
