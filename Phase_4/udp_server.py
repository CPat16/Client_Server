# This file implements the server process
import socket
import io
import os
import sys
from time import sleep
from time import time
from threading import Thread
from random import randint, seed

from PacketHandler import Packet
from udp_timer import Timer


class Server(Thread):
    def __init__(self, crpt_data, crpt_ack, data_loss, ack_loss):
        """
        Initializes Server Process
        """
        Thread.__init__(self)                   # initializes as thread
        host_ip = '127.0.0.1'
        server_port = 20001
        server_addr = (host_ip, server_port)    # address of server (IP, Port)

        self.pkt_size = 1024                                # packet size
        self.header_size = 4                                # bytes of header data
        self.data_size = self.pkt_size - self.header_size   # Size of data in packet
        # relative path of image to send
        self.img_to_send = 'hello.jpg'
        # filename to save received image
        self.img_save_to = 'server_img.jpg'

        self.crpt_data_rate = crpt_data         # packet corruption rate in percent
        self.crpt_ack_rate = crpt_ack           # recived ACK corruption rate inpercent
        self.pkt_loss_rate = data_loss          # loss of data packet rate
        self.ack_loss_rate = ack_loss           # loss of ack packet rate
        self.err_flag = 0

        seed(42)

        # create UDP server socket
        self.server_socket = socket.socket(family=socket.AF_INET,
                                           type=socket.SOCK_DGRAM)

        # Recieving sockets timeout after 2 seconds
        self.server_socket.settimeout(2)

        # bind to the socket
        try:
            self.server_socket.bind(server_addr)
            print("Server bound to port", server_port)

        except:
            print("Server failed bind to port", server_port)

    def gen_err_flag(self):
        self.err_flag = randint(1, 100)

    def send_img(self, filename):
        """
        Sends the image packet by packet

        Parameters:
          filename - file to send
        """
        recv_data = b''         # bytes for data received
        recv_pkt = Packet()     # init empty packet for received data
        read_data = b''         # byte string data read from file
        seq_num = 0             # init sequence number
        my_timer = Timer()      # Timer thread
        my_timer.set_time(0.05)    # set timer to 50 ms
        my_timer.stop()         # so timer doesn't start counting
        my_timer.start()        # start timer thread

        # open file to be sent
        print("Server: Sending image to client")
        start = time()
        with open(filename, 'rb') as img:
            read_data = img.read(self.data_size)
            # pack
            send_pkt = Packet(seq_num=seq_num, data=read_data)
            packed = send_pkt.pkt_pack()

            # send data until end of file reached
            while read_data:

                if (self.crpt_data_rate > 0 or self.crpt_ack_rate > 0 or
                        self.pkt_loss_rate > 0 or self.ack_loss_rate > 0):
                    self.gen_err_flag()

                # corrupt 1 byte of the sent packet
                if self.crpt_data_rate > 0 and self.err_flag <= self.crpt_data_rate:
                    crptpacked = b"".join([packed[0:1023], b"\x00"])
                    self.server_socket.sendto(crptpacked, self.client_addr)
                elif self.pkt_loss_rate > 0 and self.err_flag <= self.pkt_loss_rate:
                    pass    # dont send anything
                else:
                    self.server_socket.sendto(packed, self.client_addr)

                my_timer.restart()
                if self.pkt_loss_rate > 0 and self.err_flag <= self.pkt_loss_rate:
                    while not my_timer.get_exception():
                        sleep(0.0001)
                else:
                    # wait for ACK
                    recv_data = self.server_socket.recv(self.pkt_size)

                if self.ack_loss_rate > 0 and self.err_flag <= self.ack_loss_rate:
                    while not my_timer.get_exception():
                        sleep(0.0001)
                else:
                    my_timer.stop()

                    # corrupt 1 byte of the recived ACK packet
                    if self.crpt_ack_rate > 0 and self.err_flag <= self.crpt_ack_rate:
                        recv_data = b"".join([recv_data[0:1023], b"\x00"])

                    recv_pkt.pkt_unpack(recv_data)

                    # Received NAK or incorrect ACK
                    if recv_pkt.seq_num != seq_num or recv_pkt.csum != recv_pkt.checksum(recv_pkt.seq_num, recv_pkt.data):
                        pass
                    # ACK is OK, move to next data and sequence
                    else:
                        seq_num ^= 1
                        read_data = img.read(self.data_size)
                        # pack
                        send_pkt = Packet(seq_num=seq_num, data=read_data)
                        packed = send_pkt.pkt_pack()

        my_timer.kill()
        my_timer.join()
        end = time()
        print("Server: Time to send image:", end - start)

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
        self.err_flag = 0

        # get image data from server until all data received
        while True:
            try:
                if img_not_recvd:
                    print("Server: Ready to receive image", flush=True)

                recv_data = self.server_socket.recv(self.pkt_size)

                pkt.pkt_unpack(recv_data)
                if pkt.seq_num != exp_seq or pkt.csum != pkt.checksum(pkt.seq_num, pkt.data):
                    ack = Packet(exp_seq ^ 1, "ACK")
                else:
                    save_data += pkt.data
                    ack = Packet(exp_seq, "ACK")
                    exp_seq ^= 1

                ack_pack = ack.pkt_pack()
                self.server_socket.sendto(ack_pack, self.client_addr)

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
                        server_img.write(save_data)
                    print("Server: Received and saved image", flush=True)
                    break   # exit loop

    def run(self):
        """
        Runs when Server process has started
        """
        print("Server: Started")
        i = 0       # index of timeouts

        while True:
            try:
                print("Server: Ready", flush=True)
                # get request and address from client
                msg = b''           # set message to empty string
                recv_data = b''     # set received data to empty string
                msg_pkt = Packet()  # init empty packet
                (recv_data, self.client_addr) = self.server_socket.recvfrom(
                    self.pkt_size)
                i = 0   # reset timeout index
                #print("got data")
                msg_pkt.pkt_unpack(recv_data)
                #print("Received message:", msg_pkt)

                if msg_pkt.csum != msg_pkt.checksum(msg_pkt.seq_num, msg_pkt.data):
                    # send NAK
                    nak_seq = msg_pkt.seq_num ^ 0x01
                    ack = Packet(nak_seq, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)
                else:
                    msg = msg_pkt.data.decode()
                    print("Server: Client request:", msg, flush=True)

            except socket.timeout:
                i = i + 1
                if(i < 6):
                    pass
                # if the server has waited through 6 timeouts (12 seconds), exit
                else:
                    print("Server: I'm tired of waiting", flush=True)
                    break

            # if any message recieved, then service it
            if msg:
                # ------------------ Send image to client ------------------
                if msg == "download":
                    print("Server: Send ACK")
                    ack = Packet(msg_pkt.seq_num, "ACK")
                    #print("ACK:", ack)
                    ack_pack = ack.pkt_pack()
                    #print(int.from_bytes(ack_pack[(len(ack_pack)-2):len(ack_pack)], byteorder='big', signed=False))
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    # break
                    self.send_img(self.img_to_send)

                # ------------------ Get image from client ------------------
                elif msg == "upload":
                    print("Server: Send ACK")
                    ack = Packet(msg_pkt.seq_num, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    self.recv_img(self.img_save_to)

                # ------------------ Exit server process ------------------
                elif msg == "exit":
                    print("Server: Send ACK")
                    ack = Packet(msg_pkt.seq_num, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    print("Server: Exiting...")
                    break

                # ------------------ Handle invalid request ------------------
                else:
                    # send NAK
                    nak_seq = msg_pkt.seq_num ^ 0x01
                    ack = Packet(nak_seq, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    print("Server: Received invalid request:", msg)

        # close socket when finished
        self.server_socket.close()
