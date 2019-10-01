# This file implements the client process
import socket
import io
import os

def client():  
  host_ip = '127.0.0.1'
  server_port = 20001
  server_addr = (host_ip, server_port)  # address of server
  
  buf_size = 1024                   # udp buffer size
  img_to_send = 'kenobi.jpg'        # relative path of image to send
  img_save_to = 'client_img.jpg'    # filename to save received image
  img_data = b''                    # byte string to hold image data
  
  # create UDP client socket
  client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
  
  # Say hello to the server
  client_socket.sendto(str.encode("Hello there"),server_addr)
  
  # ------------------ Get image from server ------------------
  # receive image size from server
  img_size_bytes = client_socket.recv(buf_size)
  img_size = int.from_bytes(img_size_bytes, 'big')
  
  # let the server know size of image has been received
  client_socket.sendto(str.encode("Size recieved"),server_addr)
  
  # get image data from server until all data received
  while img_size > 0:
    recv_data = client_socket.recv(buf_size)
    img_data += recv_data
    img_size -= len(recv_data)
  
  # write data into a file
  with open(img_save_to, 'wb+') as client_img:
    client_img.write(img_data)
  print("Client: Received and saved image")

  # ------------------ Reply with image ------------------
  # Get size of the image to send
  img_size = os.path.getsize(img_to_send)

  # send image size in bytes to server
  client_socket.sendto(img_size.to_bytes(8, 'big'), server_addr)

  # confirm server received size
  msg = client_socket.recvfrom(buf_size)
  print("Client: Server says {}".format(msg[0].decode()))

  # open file to be sent
  print("Client: Sending image to server")
  with open(img_to_send, 'rb') as img:
    img_data = img.read(buf_size)

    # send data until end of file reached
    while img_data:
      client_socket.sendto(img_data, server_addr)
      img_data = img.read(buf_size)
  
  # close socket when finished
  client_socket.close()