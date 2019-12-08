# This file implements the client process
import socket
import io
import os
import sys
from time import sleep
from time import time
from threading import Thread

from PacketHandler import Packet
from udp_timer import Timer


class Client(Thread):
    def __init__(self):
        """
        Initializes Server Process
        """
        Thread.__init__(self)                   # initializes as thread
        host_ip = '127.0.0.1'
        server_port = 20001
        # address of server (IP, Port)
        self.server_addr = (host_ip, server_port)

        self.pkt_size = 1024                                # packet size
        self.header_size = 4                                # bytes of header data
        self.data_size = self.pkt_size - self.header_size   # Size of data in packet
        # relative path of image to send
        self.img_to_send = 'hello.jpg'
        # filename to save received image
        self.img_save_to = 'client_img.jpg'

        self.N = 10      # set N to 10 for go-back-N frame size

        # create UDP client socket
        self.client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

        # Recieving sockets timeout after 5 seconds
        self.client_socket.settimeout(5)

    def resend_window(self, window):
        for pkt in window:
            self.client_socket.sendto(pkt, self.server_addr)

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
        base = 0                # init base packet number
        window = []             # init window as empty list
        win_idx = 0             # index to item in window
        last_sent = None
        my_timer = Timer()      # Timer thread
        my_timer.set_time(0.1)    # set timer to 100 ms
        my_timer.stop()         # so timer doesn't start counting
        my_timer.start()        # start timer thread

        self.client_socket.settimeout(0)    # don't block when waiting for ACKs

        # open file to be sent
        print("Client: Sending image to server")
        # start = time()
        with open(filename, 'rb') as img:
            read_data = img.read(self.data_size)
            # pack
            send_pkt = Packet(seq_num=seq_num, data=read_data)
            packed = send_pkt.pkt_pack()

            # add first packet to window list
            window.append(packed)

            # send data until end of file reached
            while read_data or len(window) > 0:
                if my_timer.get_exception():
                    self.resend_window(window)
                    my_timer.restart()

                win_idx = len(window) - 1
                if seq_num < (base + self.N) and window[win_idx] != last_sent:
                    self.client_socket.sendto(window[win_idx], self.server_addr)
                    last_sent = window[win_idx]
                    if base == seq_num:
                        my_timer.restart()  # start timer
                    seq_num += 1

                # wait for ACK
                if recv_data:
                    recv_data = b''     # empty data buffer
                try:
                    recv_data = self.client_socket.recv(self.pkt_size)
                except socket.error as e:
                    if e == 10035:
                        pass

                if recv_data:
                    recv_pkt.pkt_unpack(recv_data)

                    # Received NAK
                    if recv_pkt.csum != recv_pkt.checksum(recv_pkt.seq_num, recv_pkt.data):
                        pass
                    # ACK is OK
                    else:
                        base = recv_pkt.seq_num + 1     # increment base
                        window.pop(0)                   # remove acked packet from window
                        if base == seq_num:
                            my_timer.stop()
                        else:
                            my_timer.restart()
                # Move to next data 
                if len(window) < self.N and read_data:
                    read_data = img.read(self.data_size)
                    # pack
                    send_pkt = Packet(seq_num=seq_num, data=read_data)
                    packed = send_pkt.pkt_pack()
                    window.append(packed)   # add packet to window
                sleep(0.0001)

        # end = time()
        my_timer.kill()
        my_timer.join()
        self.client_socket.settimeout(5)    # reset timeout value

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
        ack = Packet(-1, "ACK")     # make initial NAK

        # get image data from client until all data received
        while True:
            try:
                if img_not_recvd:
                    print("Client: Ready to receive image", flush=True)
                # start = time()
                recv_data = self.client_socket.recv(self.pkt_size)

                pkt.pkt_unpack(recv_data)
                if pkt.seq_num != exp_seq or pkt.csum != pkt.checksum(pkt.seq_num, pkt.data):
                    pass
                else:
                    save_data += pkt.data
                    ack = Packet(exp_seq, "ACK")
                    exp_seq += 1

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

        sleep(5)

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

