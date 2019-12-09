# This file implements the server process
import socket
import io
import os
import sys
from time import sleep
from time import time
from threading import Thread
from random import randint, seed
from math import ceil

from PacketHandler import Packet
from tcp_timer import Timer


class Server(Thread):
    def __init__(self, crpt_data, data_loss):
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
        self.pkt_loss_rate = data_loss          # loss of data packet rate
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
        for pkt in range(self.N):
            if pkt >= len(window):
                break
            self.server_socket.sendto(window[pkt], self.client_addr)

    def est_timeout(self, sample_rtt):
        a = 0.125
        B = 0.25
        self.est_rtt = ((1-a)*self.est_rtt) + (a*sample_rtt)
        self.dev_rtt = ((1-B)*self.dev_rtt) + (B*abs(sample_rtt - self.est_rtt))

        return self.est_rtt + (4*self.dev_rtt)

    def est_connection(self, syn_pkt: Packet):
        self.client_port = syn_pkt.src
        my_syn = Packet(self.server_port, self.client_port,
                        0, syn_pkt.ack_num + 1,
                        b'', 0x12)    # ack bit = 1, syn bit = 1
        packed = my_syn.pkt_pack()
        self.server_socket.sendto(packed, self.client_addr)

        try:
            syn_ack = Packet()
            recv_data = self.server_socket.recv(self.pkt_size)
            syn_ack.pkt_unpack(recv_data)

            if syn_ack.get_ack_bit() and syn_ack.ack_num == 1:
                self.conn_est = True
                print("Server: Connection established")
            else:
                print("Server: Connection failed: bad SYNACK")
        except socket.timeout:
            print("Server: Connection failed: timeout")

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
        dupl_cnt = 0       # count of duplicate acks
        my_timer = Timer()      # Timer thread
        my_timer.set_time(0.1)    # set timer to 100 ms
        my_timer.stop()         # so timer doesn't start counting
        my_timer.start()        # start timer thread

        # sample_rtt = 0          # init sample rtt

        self.server_socket.settimeout(0)    # don't block when waiting for ACKs

        # open file to be sent
        print("Server: Sending image to client")
        start = time()
        with open(filename, 'rb') as img:
            read_data = img.read(self.data_size)
            # pack
            send_pkt = Packet(src=self.server_port,
                              dst=self.client_port,
                              seq_num=seq_num,
                              ack_num=0,
                              data=read_data,
                              ctrl_bits=0x00)
            next_pkt = send_pkt.pkt_pack()

            # add first packet to window list
            window.append(next_pkt)

            # send data until all data acked
            while read_data or len(window) > 0:
                if (self.crpt_data_rate > 0 or self.pkt_loss_rate > 0):
                    self.gen_err_flag()

                if my_timer.get_exception():
                    self.N = ceil(self.N / 2)
                    self.resend_window(window)
                    my_timer.restart()

                # Move to next data 
                if len(window) < self.N and read_data:
                    read_data = img.read(self.data_size)
                    # pack
                    if read_data:
                        send_pkt = Packet(src=self.server_port,
                                          dst=self.client_port,
                                          seq_num=seq_num,
                                          ack_num=0,
                                          data=read_data,
                                          ctrl_bits=0x00)
                        next_pkt = send_pkt.pkt_pack()
                        window.append(next_pkt)   # add packet to window
                    else:   # no more data to be sent
                        next_pkt = None

                if next_pkt:
                    if self.crpt_data_rate > 0 and self.err_flag <= self.crpt_data_rate:
                        # corrupt 1 byte of the sent packet
                        crptpacked = b"".join([next_pkt[0:1023], b"\x00"])
                        self.server_socket.sendto(crptpacked, self.client_addr)
                    elif self.pkt_loss_rate > 0 and self.err_flag <= self.pkt_loss_rate:
                        pass    # dont send anything
                    else:
                        # send normally
                        self.server_socket.sendto(next_pkt, self.client_addr)
                    next_pkt = None
                    if base == seq_num:
                        my_timer.restart()  # start timer
                    seq_num += len(send_pkt.data)

                # receive ACK
                if recv_data:
                    recv_data = b''     # empty data buffer
                try:
                    recv_data = self.server_socket.recv(self.pkt_size)
                except socket.error as e:
                    if e == 10035:
                        pass

                if recv_data:
                    recv_pkt.pkt_unpack(recv_data)

                    # Received NAK
                    if recv_pkt.csum != recv_pkt.checksum():
                        pass
                    # ACK is OK
                    else:
                        if recv_pkt.ack_num > base:
                            dupl_cnt = 0                    # reset duplicate count
                            base = recv_pkt.ack_num         # increment base
                            window.pop(0)                   # remove acked packet from window
                            if len(window) == 0:            # no unacked packets
                                my_timer.stop()
                            else:                           # unacked packets remaining
                                my_timer.restart()
                            self.N += 1
                        elif recv_pkt.ack_num == base:
                            dupl_cnt += 1
                        # received 3 duplicate ACKs
                        if dupl_cnt >= 3:
                            dupl_cnt = 0
                            self.N = ceil(self.N / 2)
                            self.resend_window(window)
                            my_timer.restart()

                sleep(0.0001)

        end = time()
        my_timer.kill()
        my_timer.join()
        self.N = 1                          #reset window size
        # self.est_rtt = 0.1                  # reset estimated rtt
        # self.dev_rtt = 0                    # reset deviation
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
        img_not_recvd = True        # flag to indicate if image data hasn't started yet
        recv_done = False           # flag to indicate full image has been received
        exp_seq = 0                 # expected sequence number initially 0
        pkt = Packet()

        # get image data from server until all data received
        while not recv_done:
            try:
                if img_not_recvd:
                    print("Server: Ready to receive image", flush=True)

                recv_data = self.server_socket.recv(self.pkt_size)

                pkt.pkt_unpack(recv_data)
                if pkt.seq_num != exp_seq or pkt.csum != pkt.checksum():
                    pass
                elif pkt.get_fin_bit():
                    recv_done = True
                    exp_seq += len(pkt.data)        # increment expected sequence
                    save_data += pkt.data
                else:
                    exp_seq += len(pkt.data)        # increment expected sequence
                    save_data += pkt.data

                ack = Packet(src=self.server_port,
                             dst=self.client_port,
                             seq_num=0,
                             ack_num=exp_seq,
                             data=b'',
                             ctrl_bits=0x10)

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
                    break   # exit loop

        # write data into a file
        with open(filename, 'wb+') as server_img:
            server_img.write(save_data)
        print("Server: Received and saved image", flush=True)

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
                (recv_data, self.client_addr) = self.server_socket.recvfrom(self.pkt_size)
                i = 0   # reset timeout index
                msg_pkt.pkt_unpack(recv_data)

                msg = msg_pkt.data.decode()
                print("Server: Client request:", msg, flush=True)

            except socket.timeout:
                i = i + 1
                if(i < 6):
                    pass
                # if the server has waited through 6 timeouts (30 seconds), exit
                else:
                    print("Server: I'm tired of waiting", flush=True)
                    break
            if self.conn_est:
                # if any message recieved, then service it
                # ------------------ Send image to client ------------------
                if msg == "download":
                    ack = Packet(self.server_port, self.client_port,
                                0, msg_pkt.ack_num + 1,
                                b'', 0x10)
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    # break
                    self.send_img(self.img_to_send)

                # ------------------ Get image from client ------------------
                elif msg == "upload":
                    ack = Packet(self.server_port, self.client_port,
                                0, msg_pkt.ack_num + 1,
                                b'', 0x10)
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    self.recv_img(self.img_save_to)

                # ------------------ Exit server process ------------------
                elif msg == "exit":
                    ack = Packet(self.server_port, self.client_port,
                                0, msg_pkt.ack_num + 1,
                                b'', 0x10)
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)
                    # send FIN packet
                    fin = Packet(self.server_port, self.client_port, 0, 0, b'', 0x01)
                    fin_pack = fin.pkt_pack()
                    self.server_socket.sendto(fin_pack, self.client_addr)

                    fin_ack = Packet()
                    recv_data = self.server_socket.recv(self.pkt_size)
                    fin_ack.pkt_unpack(recv_data)

                    if fin_ack.get_ack_bit:
                        print("Server: Connection closed")
                        print("Server: Exiting...")
                        break
                    else:
                        print("Server: Connection teardown failed")

                # ------------------ Handle invalid request ------------------
                else:
                    # send NAK
                    ack = Packet(self.server_port, self.client_port,
                                0, 0,
                                b'', 0x10)
                    ack_pack = ack.pkt_pack()
                    self.server_socket.sendto(ack_pack, self.client_addr)

                    print("Server: Received invalid request:", msg)
                    # break
            elif msg_pkt.get_syn_bit and not self.conn_est:
                print("Server: Establishing Connection...")
                self.est_connection(msg_pkt)
            else:
                print("Server: Connection not established yet")
                # send NAK
                ack = Packet(self.server_port, self.client_port,
                             0, 0,
                             b'', 0x10)
                ack_pack = ack.pkt_pack()
                self.server_socket.sendto(ack_pack, self.client_addr)


        # close socket when finished
        self.server_socket.close()
