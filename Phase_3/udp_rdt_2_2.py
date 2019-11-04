from udp_client import Client
from udp_server import Server

# Runs process
serv_thread = Server()  # init server thread
client_thread = Client()  # init server thread

serv_thread.start()     # start server thread
client_thread.start() # start client thread

serv_thread.join()      # wait for server thread to end
client_thread.join()  # wait for client thread to end

print("Finished transmission, closing...")