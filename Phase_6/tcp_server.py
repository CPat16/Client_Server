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
from tcp_timer import Timer


class Server(Thread):
    def __init__(self, crpt_data, crpt_ack, data_loss, ack_loss):
        """
        Initializes Server Process
        """
        Thread.__init__(self)                   # initializes as thread
        host_ip = '127.0.0.1'
        self.server_port = 20001
        server_addr = (host_ip, self.server_port)   # address of server (IP, Port)
        self.conn_est = False                       # no connection established initially

        self.pkt_size = 1024                                # packet size
        self.header_size = 18                               # bytes of header data
        self.data_size = self.pkt_size - self.header_size   # Size of data in packet
        # relative path of image to send
        self.img_to_send = 'hello.jpg'
        # filename to save received image
        self.img_save_to = 'server_img.jpg'

        self.N = 1          # set N to 1 for initial window size
        self.est_rtt = 0.1  # initial estimated rtt (100ms)
        self.dev_rtt = 0    # inital deviation in rtt for timeout

        self.crpt_data_rate = crpt_data         # packet corruption rate in percent
        self.crpt_ack_rate = crpt_ack           # recived ACK corruption rate inpercent
        self.pkt_loss_rate = data_loss          # loss of data packet rate
        self.ack_loss_rate = ack_loss           # loss of ack packet rate
        self.err_flag = 0

        seed(42)

        # create UDP server socket
        self.server_socket = socket.socket(family=socket.AF_INET,
                                           type=socket.SOCK_DGRAM)

        # Recieving sockets timeout after 5 seconds
        self.server_socket.settimeout(5)

        # bind to the socket
        try:
            self.server_socket.bind(server_addr)
            print("Server bound to port", self.server_port)

        except:
            print("Server failed bind to port", self.server_port)

    def gen_err_flag(self):
        self.err_flag = randint(1, 100)

    def resend_window(self, window):
        for pkt in window:
            self.server_socket.sendto(pkt, self.client_addr)

    def est_timeout(self, sample_rtt):
        a = 0.125
        B = 0.25
        self.est_rtt = ((1-a)*self.est_rtt) + (a*sample_rtt)
        self.dev_rtt = ((1-B)*self.dev_rtt) + (B*abs(sample_rtt - self.est_rtt))

        return self.est_rtt + (4*self.dev_rtt)

    def est_connection(self, syn_pkt: Packet):
        self.client_port = syn_pkt.src
        print("Client port:", self.client_port)
        my_syn = Packet(self.server_port, self.client_port,
                        1, syn_pkt.ack_num + 1,
                        0, 0x12)    # ack bit = 1, syn bit = 1
        packed = my_syn.pkt_pack()
        self.server_socket.sendto(packed, self.client_addr)

        try:
            syn_ack = Packet()
            recv_data = self.server_socket.recv(self.pkt_size)
            syn_ack.pkt_unpack(recv_data)

            if syn_ack.get_ack_bit() and syn_ack.ack_num == 2:
                self.conn_est = True
                print("Server: Connection established")
            else:
                print("Connection failed: bad SYNACK")
        except socket.timeout:
            print("Connection failed: timeout")

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

        self.server_socket.settimeout(0)    # don't block when waiting for ACKs

        # open file to be sent
        print("Server: Sending image to client")
        start = time()
        with open(filename, 'rb') as img:
            read_data = img.read(self.data_size)
            # pack
            send_pkt = Packet(seq_num=seq_num, data=read_data)
            packed = send_pkt.pkt_pack()

            # add first packet to window list
            window.append(packed)

            # send data until end of file reached
            while read_data or len(window) > 0:
                if (self.crpt_data_rate > 0 or self.crpt_ack_rate > 0 or
                        self.pkt_loss_rate > 0 or self.ack_loss_rate > 0):
                    self.gen_err_flag()

                if my_timer.get_exception():
                    self.resend_window(window)
                    my_timer.restart()
                win_idx = len(window) - 1
                if seq_num < (base + self.N) and window[win_idx] != last_sent:
                    # corrupt 1 byte of the sent packet
                    if self.crpt_data_rate > 0 and self.err_flag <= self.crpt_data_rate:
                        crptpacked = b"".join([window[win_idx][0:1023], b"\x00"])
                        self.server_socket.sendto(crptpacked, self.client_addr)
                    elif self.pkt_loss_rate > 0 and self.err_flag <= self.pkt_loss_rate:
                        pass    # dont send anything
                    else:
                        self.server_socket.sendto(window[win_idx], self.client_addr)
                    last_sent = window[win_idx]
                    if base == seq_num:
                        my_timer.restart()  # start timer
                    seq_num += 1

                # wait for ACK
                if recv_data:
                    recv_data = b''     # empty data buffer
                try:
                    recv_data = self.server_socket.recv(self.pkt_size)
                except socket.error as e:
                    if e == 10035:
                        pass

                if recv_data:
                    if self.ack_loss_rate > 0 and self.err_flag <= self.ack_loss_rate:
                        pass     # pretend we never got ACK
                    else:

                        # corrupt 1 byte of the recived ACK packet
                        if self.crpt_ack_rate > 0 and self.err_flag <= self.crpt_ack_rate:
                            recv_data = b"".join([recv_data[0:1023], b"\x00"])

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

        end = time()
        my_timer.kill()
        my_timer.join()
        self.server_socket.settimeout(5)    # reset timeout value
        print("Server: Time to send image:", end - start)

    def recv_img(self, filename):
        """
        Receive an image packet by packet
        Saves image to specified file

        Parameters:
          filename - file location to save image
        """
        recv_data = b''             # packet of byte string data
        save_data = b''             # data to be saved to file
        img_not_recvd = True        # flag to indicate if image has been recieved
        exp_seq = 0                 # expected sequence number initially 0
        pkt = Packet()
        self.err_flag = 0
        ack = Packet(-1, "ACK")     # make initial NAK

        # get image data from server until all data received
        while True:
            try:
                if img_not_recvd:
                    print("Server: Ready to receive image", flush=True)

                recv_data = self.server_socket.recv(self.pkt_size)

                pkt.pkt_unpack(recv_data)
                if pkt.seq_num != exp_seq or pkt.csum != pkt.checksum(pkt.seq_num, pkt.data):
                    pass
                else:
                    save_data += pkt.data
                    ack = Packet(exp_seq, "ACK")
                    exp_seq += 1

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
                msg_pkt.pkt_unpack(recv_data)

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
                    ack = Packet(msg_pkt.seq_num, "ACK")
                    #print("ACK:", ack)
                    ack_pack = ack.pkt_pack()
                    #print(int.from_bytes(ack_pack[(len(ack_pack)-2):len(ack_pack)], byteorder='big', signed=False))
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    # break
                    self.send_img(self.img_to_send)

                # ------------------ Get image from client ------------------
                elif msg == "upload":
                    ack = Packet(msg_pkt.seq_num, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    self.recv_img(self.img_save_to)

                # ------------------ Exit server process ------------------
                elif msg == "exit":
                    ack = Packet(self.server_port, self.client_port, 0, msg_pkt.ack_num + 1, 0, 0x10)
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)
                    # send FIN packet
                    fin = Packet(self.server_port, self.client_port, 0, 0, 0, 0x01)
                    fin_pack = fin.pkt_pack()
                    self.server_socket.sendto(fin_pack, self.client_addr)

                    fin_ack = Packet()
                    recv_data = self.server_socket.recv(self.pkt_size)
                    fin_ack.pkt_unpack(recv_data)

                    if fin_ack.get_ack_bit:
                        print("Server: Exiting...")
                        break
                    else:
                        print("Server: Connection teardown failed")

                # ------------------ Handle invalid request ------------------
                else:
                    # send NAK
                    nak_seq = msg_pkt.seq_num ^ 0x01
                    ack = Packet(nak_seq, "ACK")
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    print("Server: Received invalid request:", msg)
                    break

        # close socket when finished
        self.server_socket.close()
