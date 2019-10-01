# This file implements the server process
import socket
import io
import os

def server():
  host_ip = '127.0.0.1'
  server_port = 20001
  server_addr = (host_ip, server_port)  # address of server

  buf_size = 1024                   # udp buffer size
  img_to_send = 'hello.jpg'         # relative path of image to send
  img_save_to = 'server_img.jpg'    # filename to save received image
  img_data = b''                    # byte string to hold image data

  # create UDP server socket
  server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

  # bind to the socket
  try:
    server_socket.bind(server_addr)
    print("Server bound to port", server_port)

  except:
    print("Server bind failed to port", server_port)

  # get hello and address from client
  (msg, client_addr) = server_socket.recvfrom(buf_size)
  print("Server: Reached by client")
  
  # ------------------ Send image to client ------------------
  # Get size of the image to send
  img_size = os.path.getsize(img_to_send)

  # send image size in bytes to client
  server_socket.sendto(img_size.to_bytes(8, 'big'), client_addr)

  # confirm client received size
  msg = server_socket.recvfrom(buf_size)
  print("Server: Client says {}".format(msg[0].decode()))

  # open file to be sent
  print("Server: Sending image to client")
  with open(img_to_send, 'rb') as img:
    img_data = img.read(buf_size)

    # send data until end of file reached
    while img_data:
      server_socket.sendto(img_data, client_addr)
      img_data = img.read(buf_size)

  # ------------------ Get reply image ------------------
  # receive image size from client
  img_size_bytes = server_socket.recv(buf_size)
  img_size = int.from_bytes(img_size_bytes, 'big')
  
  # let the client know size of image has been received
  server_socket.sendto(str.encode("Size recieved"), client_addr)
  
  # get image data from server until all data received
  while img_size > 0:
    recv_data = server_socket.recv(buf_size)
    img_data += recv_data
    img_size -= len(recv_data)
  
  # write data into a file
  with open(img_save_to, 'wb+') as server_img:
    server_img.write(img_data)
  print("Server: Received and saved image")

  # close socket when finished
  server_socket.close()