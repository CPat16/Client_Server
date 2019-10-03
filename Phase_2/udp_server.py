# This file implements the server process
import socket
import io
import os
import sys
from threading import Thread

import udp_client

class Server(Thread):
  def __init__(self):
    """
    Initializes Server Process
    """
    Thread.__init__(self)                   # initializes as thread
    host_ip = '127.0.0.1'
    server_port = 20001
    server_addr = (host_ip, server_port)    # address of server

    self.pkt_size = 1024                    # packet size
    self.img_to_send = 'hello.jpg'          # relative path of image to send
    self.img_save_to = 'server_img.jpg'     # filename to save received image

    # create UDP server socket
    self.server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    self.server_socket.settimeout(2)

    # bind to the socket
    try:
      self.server_socket.bind(server_addr)
      print("Server bound to port", server_port)

    except:
      print("Server bind failed to port", server_port)

  def send_img(self, filename):
    """
    Sends the image packet by packet

    Parameters:
      filename - file to send
    """
    pkt = b''                          # packet of byte string data

    # Get size of the image to send
    img_size = os.path.getsize(self.img_to_send)

    # send image size in bytes to client
    self.server_socket.sendto(img_size.to_bytes(8, 'big'), self.client_addr)

    # confirm client received size
    msg = self.server_socket.recvfrom(self.pkt_size)
    print("Server: Client says {}".format(msg[0].decode()))

    # open file to be sent
    print("Server: Sending image to client")
    with open(filename, 'rb') as img:
      pkt = img.read(self.pkt_size)

      # send data until end of file reached
      while pkt:
        self.server_socket.sendto(pkt, self.client_addr)
        pkt = img.read(self.pkt_size)

  def recv_img(self, filename):
    """
    Receive an image packet by packet
    Saves image to specified file

    Parameters:
      filename - file location to save image
    """
    recv_data = b''                          # packet of byte string data

    # receive image size from client
    img_size_bytes = self.server_socket.recv(self.pkt_size)
    img_size = int.from_bytes(img_size_bytes, 'big')
    
    # let the client know size of image has been received
    self.server_socket.sendto(str.encode("Size recieved"), self.client_addr)

    # get image data from server until all data received
    while img_size > 0:
      pkt = self.server_socket.recv(self.pkt_size)
      recv_data += pkt
      img_size -= len(pkt)
    
    # write data into a file
    with open(filename, 'wb+') as server_img:
      server_img.write(recv_data)
    print("Server: Received and saved image")

  def run(self):
    """
    Runs when Server process has started
    """
    print("Server: Started")
    i = 0
    
    while True:
      try:
        # get request and address from client
        (msg, self.client_addr) = self.server_socket.recvfrom(self.pkt_size)
        msg = msg.decode()
        print("Server: Client request:", msg)

        # ------------------ Send image to client ------------------
        if msg == "download":
          self.send_img(self.img_to_send)

        # ------------------ Get image from client ------------------
        elif msg == "upload":
          self.recv_img(self.img_save_to)

        # ------------------ Exit server process ------------------
        elif msg == "exit":
          print("Server: Exiting...")
          break

      except socket.timeout:
        i = i + 1
        if(i < 5):
          print("Server: Ready")

        # if the server has waited through 5 timeouts, exit
        else:
          print("Server: I'm tired of waiting")
          break

    # close socket when finished
    self.server_socket.close()


# Runs process
serv_proc = Server()  # init server thread
client_thread = Thread(target=udp_client.client) # for testing

serv_proc.start()     # start server thread
client_thread.start() # for testing

serv_proc.join()      # wait for server thread to end
client_thread.join()  # for testing

print("Finished transmission, closing...")
