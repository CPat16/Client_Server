# This file implements the server process
import socket
import io
import os
import sys
from time import sleep
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
    server_addr = (host_ip, server_port)    # address of server (IP, Port)

    self.pkt_size = 1024                    # packet size
    self.img_to_send = 'hello.jpg'          # relative path of image to send
    self.img_save_to = 'server_img.jpg'     # filename to save received image

    # create UDP server socket
    self.server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    self.server_socket.settimeout(10)       # Recieving sockets timeout after 10 seconds

    # bind to the socket
    try:
      self.server_socket.bind(server_addr)
      print("Server bound to port", server_port)

    except:
      print("Server failed bind to port", server_port)

  def send_img(self, filename):
    """
    Sends the image packet by packet

    Parameters:
      filename - file to send
    """
    pkt = b''                          # packet of byte string data

    # open file to be sent
    print("Server: Sending image to client")
    with open(filename, 'rb') as img:
      pkt = img.read(self.pkt_size)

      # send data until end of file reached
      while pkt:
        self.server_socket.sendto(pkt, self.client_addr)
        pkt = img.read(self.pkt_size)
        sleep(0.06)   # sleep for 60 ms

  def recv_img(self, filename):
    """
    Receive an image packet by packet
    Saves image to specified file

    Parameters:
      filename - file location to save image
    """
    recv_data = b''           # packet of byte string data
    img_not_recvd = True      # flag to indicate if image has been recieved

    # get image data from server until all data received
    while True:
      try:
        print("Server: Ready to receive image")
        pkt = self.server_socket.recv(self.pkt_size)
        recv_data += pkt
        if img_not_recvd:
          img_not_recvd = False       # img data began streaming if it reaches this point
      
      except socket.timeout:
        # if image not recieved yet, keep waiting
        if img_not_recvd:
          pass
        # image has been recieved
        else:
          # write data into a file
          with open(filename, 'wb+') as server_img:
            server_img.write(recv_data)
          print("Server: Received and saved image")
          break   # exit loop
    

  def run(self):
    """
    Runs when Server process has started
    """
    print("Server: Started")
    i = 0       # index of timeouts
    msg = ''    # set message to empty string
    
    while True:
      try:
        print("Server: Ready")
        # get request and address from client
        (msg, self.client_addr) = self.server_socket.recvfrom(self.pkt_size)
        i = 0   # reset timeout index
        msg = msg.decode()
        print("Server: Client request:", msg)

      except socket.timeout:
        i = i + 1
        if(i < 6):
          pass
        # if the server has waited through 6 timeouts (60 seconds), exit
        else:
          print("Server: I'm tired of waiting")
          break

      # if any message recieved, then service it
      if msg:
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
        
        # ------------------ Handle invalid request ------------------
        else:
          print("Server: Received invalid request:", msg)

    # close socket when finished
    self.server_socket.close()


# Runs process
serv_proc = Server()  # init server thread
# client_thread = Thread(target=udp_client.client) # for testing

serv_proc.start()     # start server thread
# client_thread.start() # for testing

serv_proc.join()      # wait for server thread to end
# client_thread.join()  # for testing

print("Finished transmission, closing...")
