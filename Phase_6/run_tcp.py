from tcp_server import Server
from tcp_client import Client
from tcp_timer import Timer

crpt_data = input("Input percentage of data corruption: ")
crpt_ack = input("Input percentage of ack corruption: ")
data_loss = input("Input percentage of data packet loss: ")
ack_loss = input("Input percentage of ACK packet loss: ")

# Runs process
serv_thread = Server(int(crpt_data), int(data_loss))  # init server thread
client_thread = Client(int(crpt_ack), int(ack_loss))  # init server thread

serv_thread.start()     # start server thread
client_thread.start() # start client thread

serv_thread.join()      # wait for server thread to end
client_thread.join()  # wait for client thread to end

print("Finished transmission, closing...")