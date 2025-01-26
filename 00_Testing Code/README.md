# Testing Code
This directory presents a small project to convert `candump` files into sqlite databases. 

The program should read the `candump` file and load it into the sqlite database. The database should be indexed by the CAN arbitration identifier (can_id) before timestamp. If the can_id is broken into the SAE J1939 fields, it should be loaded according to Source Address, Parameter Group Number, and Destination Address. THis enables faster recall from the database, since often analysis is based on interactions or broadcasts between controller applications (CAs).


The original code `_0` was generated with ChatGPT. 

Some example tests should reveal the original code does not work. 

Improvements to the code are demonstrated with tests.

