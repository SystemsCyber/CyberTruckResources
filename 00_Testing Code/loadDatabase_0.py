import sqlite3
import re

# Define the database file name
db_file = "can_data.db"

# Define the candump file name
candump_file = "candump.log"

# Define a regular expression to parse candump lines
candump_pattern = re.compile(r"\((\d+\.\d+)\) ([0-9A-Fa-f]+)#([0-9A-Fa-f]*)")

def create_database(db_file):
    """Creates the SQLite database and table."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create table with primary key (id) and secondary key (timestamp)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS candata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            can_id TEXT NOT NULL,
            can_data TEXT
        )
        """
    )
    
    conn.commit()
    conn.close()


def parse_and_store_candump(db_file):
    """Parses the candump file and stores data in the SQLite database."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    with open(candump_file, "r") as file:
        for line in file:
            match = candump_pattern.match(line.strip())
            if match:
                timestamp, can_id, can_data = match.groups()
                
                # Insert the parsed data into the database
                cursor.execute(
                    "INSERT INTO candata (timestamp, can_id, can_data) VALUES (?, ?, ?)",
                    (float(timestamp), can_id, can_data)
                )

    conn.commit()
    conn.close()


def main():
    create_database(db_file)
    parse_and_store_candump(db_file)
    print("Candump data has been successfully stored in the database.")

if __name__ == "__main__":
    main()