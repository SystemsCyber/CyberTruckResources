import sqlite3
import re
import argparse
import os

# Define a regular expression to parse candump lines
candump_pattern = re.compile(r"\((\d+\.\d+)\) ([0-9A-Fa-f]+)#([0-9A-Fa-f]*)")

def parse_j1939_id(can_id_hex):
    """Parses a J1939 CAN ID into its components, handling PDU1 and PDU2 formats."""
    can_id = int(can_id_hex, 16)
    pgn = (can_id >> 8) & 0xFFFF  # PGN (bits 8-23)
    source_address = can_id & 0xFF  # Source Address (bits 0-7)

    # Determine if it's PDU1 or PDU2 format
    pdu_format = (pgn >> 8) & 0xFF  # Extract the PDU format (bits 16-23)
    if pdu_format < 240:  # PDU1 format
        destination_address = pgn & 0xFF  # Destination Address (bits 8-15)
        pgn = pgn & 0xFF00  # Clear the destination address for PDU1 PGN
    else:  # PDU2 format
        destination_address = 255  # Set destination address to 255 for PDU2

    return pgn, source_address

def create_database(db_file):
    """Creates the SQLite database and table."""
    if os.path.exists(db_file):
        os.remove(db_file)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create table with primary key (source_address) and secondary key (pgn)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS candata (
            source_address INTEGER NOT NULL,
            pgn INTEGER NOT NULL,
            can_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            can_data TEXT,
            PRIMARY KEY (source_address, pgn)
        )
        """
    )
    
    conn.commit()
    conn.close()

def parse_and_store_candump(candump_file, db_file):
    """Parses the candump file and stores data in the SQLite database."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    with open(candump_file, "r") as file:
        for line in file:
            entries = line.split()
            timestamp = float(entries[0][1:-1])
            channel = entries[1]
            can_frame =  entries[2].split("#")
            can_id_hex = can_frame[0]
            can_data = can_frame[1]

            pgn, source_address = parse_j1939_id(can_id_hex)
                
            # Insert the parsed data into the database
            cursor.execute(
                "INSERT OR IGNORE INTO candata (source_address, pgn, can_id, timestamp, can_data) VALUES (?, ?, ?, ?, ?)",
                (source_address, pgn, can_id_hex, float(timestamp), can_data)
            )

    conn.commit()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Parse a candump file and store data in SQLite database.")
    parser.add_argument("candump_file", help="Path to the candump file to be parsed.")
    parser.add_argument("--output", dest="db_file", default=None, help="Path to the output SQLite database file.")
    args = parser.parse_args()

    # Set the default database file name based on the candump file if not provided
    db_file = args.db_file or f"{args.candump_file}.db"

    create_database(db_file)
    parse_and_store_candump(args.candump_file, db_file)
    print(f"Candump data has been successfully stored in the database: {db_file}")

if __name__ == "__main__":
    main()
