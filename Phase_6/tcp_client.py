# This file implements the client process
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


class Client(Thread):
    def __init__(self, crpt_ack, ack_loss):
        """
        Initializes Server Process
        """
        Thread.__init__(self)                   # initializes as thread
        host_ip = '127.0.0.1'
        self.server_port = 20001
        self.client_port = 20002
        # address of server (IP, Port)
        self.server_addr = (host_ip, self.server_port)
        # address of client (IP, Port)
        self.client_addr = (host_ip, self.client_port)

        self.crpt_ack_rate = crpt_ack           # recived ACK corruption rate inpercent
        self.ack_loss_rate = ack_loss           # loss of ack packet rate
        self.err_flag = 0

        self.N = 1
        self.est_rtt = 0.1  # initial estimated rtt (100ms)
        self.dev_rtt = 0    # inital deviation in rtt for timeout

        self.pkt_size = 1024                                # packet size
        self.header_size = 18                                # bytes of header data
        self.data_size = self.pkt_size - self.header_size   # Size of data in packet
        # relative path of image to send
        self.img_to_send = 'hello.jpg'
        # filename to save received image
        self.img_save_to = 'client_img.jpg'

        seed(42)

        # create UDP client socket
        self.client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

        # Recieving sockets timeout after 1 seconds
        self.client_socket.settimeout(1)

        # bind to the socket
        try:
            self.client_socket.bind(self.client_addr)
            print("Client bound to port", self.client_port)

        except:
            print("Client failed bind to port", self.client_port)

    def gen_err_flag(self):
        self.err_flag = randint(1, 100)

    def est_timeout(self, sample_rtt):
        a = 0.125
        B = 0.25
        self.est_rtt = ((1-a)*self.est_rtt) + (a*sample_rtt)
        self.dev_rtt = ((1-B)*self.dev_rtt) + (B*abs(sample_rtt - self.est_rtt))

        return self.est_rtt + (4*self.dev_rtt)

    def est_connection(self):
        my_syn = Packet(src=self.client_port,
                        dst=self.server_port,
                        seq_num=0,
                        ack_num=0,
                        data=b'',
                        ctrl_bits=0x02)
        packed = my_syn.pkt_pack()
        self.client_socket.sendto(packed, self.server_addr)

        try:
            syn_ack = Packet()
            recv_data = self.client_socket.recv(self.pkt_size)
            syn_ack.pkt_unpack(recv_data)

            if syn_ack.get_ack_bit() and syn_ack.ack_num == 1:
                self.conn_est = True
                print("Client: Sending ACK for SYNACK")
                my_syn = Packet(src=self.client_port,
                        dst=self.server_port,
                        seq_num=0,
                        ack_num=1,
                        data=b'',
                        ctrl_bits=0x10)
                packed = my_syn.pkt_pack()
                self.client_socket.sendto(packed, self.server_addr)
            else:
                print("Client: Connection failed: bad SYNACK")
        except socket.timeout:
            print("Client: Connection failed: timeout")

    def resend_lost(self, window, seq):
        self.client_socket.sendto(window[seq], self.server_addr)

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
        window = {}             # init window as empty dict
        dupl_cnt = 0       # count of duplicate acks
        my_timer = Timer()      # Timer thread
        my_timer.set_time(0.1)    # set timer to 100 ms
        my_timer.stop()         # so timer doesn't start counting
        my_timer.start()        # start timer thread
        rtt_start = {}

        self.client_socket.settimeout(0)    # don't block when waiting for ACKs

        # open file to be sent
        print("Client: Sending image to server")
        # start = time()
        with open(filename, 'rb') as img:
            read_data = img.read(self.data_size)
            # pack
            send_pkt = Packet(src=self.client_port,
                              dst=self.server_port,
                              seq_num=seq_num,
                              ack_num=0,
                              data=read_data,
                              ctrl_bits=0x00)
            next_pkt = send_pkt.pkt_pack()

            # add first packet to window list
            window[send_pkt.seq_num] = next_pkt

            # send data until all data acked
            while read_data or len(window) > 0:
                # Move to next data 
                if len(window) < self.N and read_data:
                    read_data = img.read(self.data_size)
                    # pack
                    if read_data:
                        send_pkt = Packet(src=self.client_port,
                                          dst=self.server_port,
                                          seq_num=seq_num,
                                          ack_num=0,
                                          data=read_data,
                                          ctrl_bits=0x00)
                        next_pkt = send_pkt.pkt_pack()
                        window[send_pkt.seq_num] = next_pkt   # add packet to window
                    else:   # no more data to be sent
                        next_pkt = None

                if next_pkt:
                    self.client_socket.sendto(next_pkt, self.server_addr)
                    next_pkt = None
                    rtt_start[send_pkt.seq_num] = time()
                    if base == seq_num:
                        my_timer.restart()  # start timer
                    seq_num += len(send_pkt.data)

                if my_timer.get_exception():
                    self.N = ceil(self.N / 2)
                    self.resend_lost(window, base)
                    rtt_start[base] = time()
                    my_timer.restart()

                # receive ACK
                if recv_data:
                    recv_data = b''     # empty data buffer
                try:
                    recv_data = self.client_socket.recv(self.pkt_size)
                except socket.error as e:
                    if e == 10035:
                        pass

                if recv_data:
                    recv_pkt.pkt_unpack(recv_data)

                    if recv_pkt.csum != recv_pkt.checksum():
                        pass
                    # ACK is OK
                    else:
                        rtt_end = time()
                        if recv_pkt.ack_num > base:
                            dupl_cnt = 0                    # reset duplicate count
                            prev_base = base
                            base = recv_pkt.ack_num         # increment base
                            for pkt in sorted(window.keys()):   # remove acked packets from window
                                if pkt < base:
                                    window.pop(pkt)
                                else:
                                    break
                            if len(window) == 0:            # no unacked packets
                                my_timer.stop()
                            else:                           # unacked packets remaining
                                my_timer.restart(self.est_timeout(rtt_end - rtt_start[prev_base]))
                            self.N += 1
                        elif recv_pkt.ack_num == base:
                            dupl_cnt += 1
                        # received 3 duplicate ACKs
                        if dupl_cnt >= 3:
                            dupl_cnt = 0
                            self.N = ceil(self.N / 2)
                            self.resend_lost(window, base)
                            rtt_start[base] = time()
                            my_timer.restart()

                sleep(0.0001)

        # end = time()
        my_timer.kill()
        my_timer.join()
        self.N = 1                          #reset window size
        self.est_rtt = 0.1                  # reset estimated rtt
        self.dev_rtt = 0                    # reset deviation
        self.client_socket.settimeout(1)    # reset timeout value

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
        exp_seq = 0                 # expected sequence number initially 0
        chunks = {}                 # init dictionary of received data chunks
        pkt = Packet()

        # get image data from server until all data received
        while True:
            try:
                if (self.crpt_ack_rate > 0 or self.ack_loss_rate > 0):
                    self.gen_err_flag()

                if img_not_recvd:
                    print("Client: Ready to receive image", flush=True)

                recv_data = self.client_socket.recv(self.pkt_size)

                pkt.pkt_unpack(recv_data)
                if pkt.seq_num < exp_seq or pkt.csum != pkt.checksum():
                    pass
                elif pkt.seq_num > exp_seq:
                    if pkt.seq_num not in chunks.keys():
                        chunks[pkt.seq_num] = pkt.data
                else:
                    chunks[pkt.seq_num] = pkt.data
                    # increment expected sequence to highest received data
                    exp_seq += len(pkt.data)
                    while exp_seq in chunks.keys():
                        exp_seq += len(chunks[exp_seq])

                ack = Packet(src=self.client_port,
                             dst=self.server_port,
                             seq_num=0,
                             ack_num=exp_seq,
                             data=b'',
                             ctrl_bits=0x10)

                ack_pack = ack.pkt_pack()

                if (self.ack_loss_rate > 0 and self.err_flag <= self.ack_loss_rate):
                    pass
                elif (self.crpt_ack_rate > 0 and self.err_flag <= self.crpt_ack_rate):
                    ack_pack = b"".join([ack_pack[0:1023], b"\x01"])
                    self.client_socket.sendto(ack_pack, self.server_addr)
                else:
                    self.client_socket.sendto(ack_pack, self.server_addr)

                if img_not_recvd:
                    img_not_recvd = False       # img data began streaming if it reaches this point

            except socket.timeout:
                # if image not recieved yet, keep waiting
                if img_not_recvd:
                    pass
                # image has been recieved
                else:
                    break   # exit loop

        for chunk in sorted(chunks.keys()):
            save_data += chunks[chunk]
        # write data into a file
        with open(filename, 'wb+') as client_img:
            client_img.write(save_data)
        print("Client: Received and saved image", flush=True)

    def run(self):
        """
        Runs when Client process has started
        """
        print("Client: Started", flush=True)
        ack = Packet()
        ack_data = b''

        self.est_connection()

        request = "download"
        req_pkt = Packet(src=self.client_port,
                         dst=self.server_port,
                         seq_num=0,
                         ack_num=0,
                         data=request,
                         ctrl_bits=0x00)
        req_packed = req_pkt.pkt_pack()

        self.client_socket.sendto(req_packed, self.server_addr)

        ack_data = self.client_socket.recv(self.pkt_size)
        ack.pkt_unpack(ack_data)

        self.recv_img(self.img_save_to)

        ack = Packet()
        ack_data = b''
        request = "upload"
        req_pkt = Packet(src=self.client_port,
                         dst=self.server_port,
                         seq_num=0,
                         ack_num=0,
                         data=request,
                         ctrl_bits=0x00)
        req_packed = req_pkt.pkt_pack()

        self.client_socket.sendto(req_packed, self.server_addr)

        ack_data = self.client_socket.recv(self.pkt_size)
        ack.pkt_unpack(ack_data)

        self.send_img(self.img_to_send)

        sleep(5)

        ack = Packet()
        ack_data = b''
        request = "exit"
        req_pkt = Packet(src=self.client_port,
                             dst=self.server_port,
                             seq_num=0,
                             ack_num=0,
                             data=request,
                             ctrl_bits=0x01)
        req_packed = req_pkt.pkt_pack()

        self.client_socket.sendto(req_packed, self.server_addr)

        ack_data = self.client_socket.recv(self.pkt_size)
        ack.pkt_unpack(ack_data)
        fin = Packet()
        fin_data = self.client_socket.recv(self.pkt_size)
        fin.pkt_unpack(fin_data)

        ack = Packet(src=self.client_port,
                     dst=self.server_port,
                     seq_num=0,
                     ack_num=0,
                     data=b'',
                     ctrl_bits=0x10)

        ack_pack = ack.pkt_pack()
        self.client_socket.sendto(ack_pack, self.server_addr)
        print("Client: Connection closed")

        print("Client: Exiting...")
        # close socket when finished
        self.client_socket.close()

