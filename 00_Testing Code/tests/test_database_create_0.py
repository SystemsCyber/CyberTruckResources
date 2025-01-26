from loadDatabase_0 import * #Import the file with the function to test
import os

def test_create_db(faker):
    # Define the database file name
    db_file = faker.file_name()

    #Call the function to be tested
    create_database(db_file)

    #Confirm the new file was created
    assert os.path.exists(db_file)

    #clean up after the test is completed
    os.remove(db_file)

