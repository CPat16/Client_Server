Network Design
Project - Phase 1
Christian Patterson

Files Submitted:
 - udp_client.py
    Implements client process - reaches out to server, receives an image and replies with an image
 - udp_server.py
    Implements server process - waits for client to reach out, sends image and receives image in reply
 - udp_trans_runner.py
    Creates threads to run the client and server processes in parallel
 - hello.jpg, kenobi.jpg
    Image files to be transmitted

To Execute:
 - Must have Python installed (I used Python 3.7.4)
 - In your terminal (GitBash, cmd.exe, etc.) change directory to where the source files are saved
 - Run the python file udp_trans_runner.py by entering `python udp_trans_runner.py` in your terminal
 - After execution, client_img.jpg and server_img.jpg should appear in the same folder,
    these are the files where the client and server saved the images they received.