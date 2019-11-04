# This file implements the client process
import socket
import io
import os
import sys
from time import sleep
from time import time
from threading import Thread

from PacketHandler import Packet

class Client(Thread):
  def __init__(self):
    """
    Initializes Server Process
    """
    Thread.__init__(self)                   # initializes as thread
    host_ip = '127.0.0.1'
    server_port = 20001
    self.server_addr = (host_ip, server_port)    # address of server (IP, Port)

    self.pkt_size = 1024                                # packet size
    self.header_size = 4                                # bytes of header data
    self.data_size = self.pkt_size - self.header_size   # Size of data in packet
    self.img_to_send = 'hello.jpg'                      # relative path of image to send
    self.img_save_to = 'client_img.jpg'                 # filename to save received image

    # create UDP client socket
    self.client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    self.client_socket.settimeout(2)       # Recieving sockets timeout after 10 seconds


  def send_img(self, filename):
    """
    Sends the image packet by packet

    Parameters:
      filename - file to send
    """
    recv_data = b''       # bytes for data received
    recv_pkt = Packet()   # init empty packet for received data
    read_data = b''       # byte string data read from file
    seq_num = 0           # init sequence number
    
    # open file to be sent
    print("Client: Sending image to Server")
    with open(filename, 'rb') as img:
      read_data = img.read(self.data_size)

      # send data until end of file reached
      while read_data:
        # pack and send
        send_pkt = Packet(seq_num=seq_num, data=read_data)
        packed = send_pkt.pkt_pack()
        self.client_socket.sendto(packed, self.server_addr)
        #print("Client: Sent:", send_pkt)
        
        # wait for ACK
        recv_data = self.client_socket.recv(self.pkt_size)
        recv_pkt.pkt_unpack(recv_data)

        #print("Client: Received message:", recv_pkt)

        # Received NAK or incorrect ACK
        if recv_pkt.seq_num != seq_num or recv_pkt.csum != recv_pkt.checksum(recv_pkt.seq_num, recv_pkt.data):
          print("Client: Received NAK or corrupted ACK, Resending...")
        # ACK is OK, move to next data and sequence
        else:
          #print("Client: got ok packet")
          seq_num ^= 1
          read_data = img.read(self.data_size)
   
  def recv_img(self, filename):
    """
    Receive an image packet by packet
    Saves image to specified file

    Parameters:
      filename - file location to save image
    """
    recv_data = b''           # packet of byte string data
    save_data = b''           # data to be saved to file
    img_not_recvd = True      # flag to indicate if image has been recieved
    exp_seq = 0               # expected sequence number initially 0
    pkt = Packet()

    # get image data from client until all data received
    while True:
      try:
        if img_not_recvd:
          print("Client: Ready to receive image", flush=True)
        # start = time()
        recv_data = self.client_socket.recv(self.pkt_size)
        
        pkt.pkt_unpack(recv_data)
        if pkt.seq_num != exp_seq or pkt.csum != pkt.checksum(pkt.seq_num, pkt.data):
          ack = Packet(exp_seq^1, "ACK")
        else:
          save_data += pkt.data
          ack = Packet(exp_seq, "ACK")
          exp_seq ^= 1

        ack_pack = ack.pkt_pack()
        self.client_socket.sendto(ack_pack, self.server_addr)
        
        if img_not_recvd:
          img_not_recvd = False       # img data began streaming if it reaches this point
      
      except socket.timeout:
        # if image not recieved yet, keep waiting
        if img_not_recvd:
          pass
        # image has been recieved
        else:
          # write data into a file
          # end = time()
          # print("Client: Time to receive image:", end - start - 2)
          with open(filename, 'wb+') as server_img:
            server_img.write(save_data)
          print("Client: Received and saved image", flush=True)
          break   # exit loop

  def run(self):
    """
    Runs when Client process has started
    """
    print("Client: Started", flush=True)
    ack = Packet()
    ack_data = b''

    request = "download"
    req_pkt = Packet(0, request)
    req_packed = req_pkt.pkt_pack()
    
    self.client_socket.sendto(req_packed, self.server_addr)

    ack_data = self.client_socket.recv(self.pkt_size)
    ack.pkt_unpack(ack_data)

    self.recv_img(self.img_save_to)

    ack = Packet()
    ack_data = b''
    request = "upload"
    req_pkt = Packet(0, request)
    req_packed = req_pkt.pkt_pack()
    
    self.client_socket.sendto(req_packed, self.server_addr)

    ack_data = self.client_socket.recv(self.pkt_size)
    ack.pkt_unpack(ack_data)

    self.send_img(self.img_to_send)

    sleep(2)
    
    ack = Packet()
    ack_data = b''
    request = "exit"
    req_pkt = Packet(0, request)
    req_packed = req_pkt.pkt_pack()
    
    self.client_socket.sendto(req_packed, self.server_addr)

    ack_data = self.client_socket.recv(self.pkt_size)
    ack.pkt_unpack(ack_data)

    print("Client: Exiting...")
    # close socket when finished
    self.client_socket.close()


if __name__ == "__main__":
  # Runs process
  client_thread = Client()  # init server thread
  #client_thread = Thread(target=udp_client.client) # for testing

  client_thread.start()     # start server thread
  #client_thread.start() # for testing

  client_thread.join()      # wait for server thread to end
  #client_thread.join()  # for testing

  print("Finished transmission, closing...")
