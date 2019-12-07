# This file contains the Packet class which handles packing functions
import struct

"""
TCP packet implementation:
 <---------------------- 32 ----------------------->
|       src port         |          dst port        |
|                       seq                         |
|                       ack                         |
 <-- 8 --> <----- 8 ----> <--------- 16 ----------->
| headlen |00|U|A|P|R|S|F|      recv window         |
|       csum             |          data...         |
|                   data...                         |
                        .
                        .
                        .
|                       data                        |
total size = 1024
head len = 144
NOTE: Urget Data pointer and options not needed for implementation
"""

class Packet():
    """
    src     - source port
    dst     - destination port
    seq_num - sequence number
    ack_num - ACK number
    """
    def __init__(self, src=-1, dst=-1, seq_num=-1, ack_num=-1, data=b'', ctrl_bits=0x00):
        self.src = src
        self.dst = dst
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.head_len = 144         # header length
        self.ctrl_bits = ctrl_bits  # control bits
        self.rwin = 4096            # receive window
        self.data = data
        if(seq_num >= 0):
            self.csum = self.checksum()
        else:
            self.csum = -1
        self.fmt = '!HHLLBBHH' + 'B'*len(self.data)
    def __repr__(self):
        return ("\nsrc: {0} | dst: {1}\nseq_num: {2}\nack_num: {3}\nhead_len: {4} | ctrl_bits: {5:b} | rwin: {6}\ncsum: {7}\ndata: {8}\n".format(
                    self.src, self.dst, self.seq_num, self.ack_num, self.head_len, self.ctrl_bits, self.rwin, self.csum, self.data))

    def get_ack_bit(self):
        return (self.ctrl_bits >> 4) & 0x01

    def get_syn_bit(self):
        return (self.ctrl_bits >> 1) & 0x01

    def get_fin_bit(self):
        return self.ctrl_bits & 0x01

    def set_ack_bit(self):
        self.ctrl_bits = self.ctrl_bits | 0x10

    def set_syn_bit(self):
        self.ctrl_bits = self.ctrl_bits | 0x02

    def set_fin_bit(self):
        self.ctrl_bits = self.ctrl_bits | 0x01

    def pkt_pack(self):
        if isinstance(self.data, str):
            data = self.data.encode()
        else:
            data = self.data
        return struct.pack(self.fmt, self.src, self.dst, self.seq_num, self.ack_num,
                            self.head_len, self.ctrl_bits, self.rwin, self.csum, *data)

    def pkt_unpack(self, packed):
        self.src = int.from_bytes(packed[0:2], byteorder='big', signed=False)
        self.dst = int.from_bytes(packed[2:4], byteorder='big', signed=False)
        self.seq_num = int.from_bytes(packed[4:8], byteorder='big', signed=False)
        self.ack_num = int.from_bytes(packed[8:12], byteorder='big', signed=False)
        self.head_len = int.from_bytes(packed[12:13], byteorder='big', signed=False)
        self.ctrl_bits = int.from_bytes(packed[13:14], byteorder='big', signed=False)
        self.rwin = int.from_bytes(packed[14:16], byteorder='big', signed=False)
        self.csum = int.from_bytes(packed[16:18], byteorder='big', signed=False)
        self.data = packed[18:len(packed)]

    def carry_around_add(self, a, b):
        c = a + b
        return (c & 0xffff) + (c >> 16)

    def checksum(self):
        csum = 0
        msg = self.data
        if isinstance(msg, str):
            msg = msg.encode()
        if isinstance(msg, (bytearray, bytes)):
            msg = int.from_bytes(msg, byteorder='big', signed=False)

        # add header to checksum except csum field
        csum = self.carry_around_add(csum, self.src)
        csum = self.carry_around_add(csum, self.dst)
        csum = self.carry_around_add(csum, self.seq_num)
        csum = self.carry_around_add(csum, self.ack_num)
        csum = self.carry_around_add(csum, self.head_len)
        csum = self.carry_around_add(csum, self.ctrl_bits)
        csum = self.carry_around_add(csum, self.rwin)

        # add data to csum
        while msg != 0:
            next_bits = msg & 0xffff
            csum = self.carry_around_add(csum, next_bits)
            msg = msg >> 16
        return ~csum & 0xffff

if __name__ == "__main__":
    #msg = b'\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01'
    msg = "checksum2"
    # int_msg = int.from_bytes(msg, byteorder='big', signed=False)
    # print(bin(int_msg))
    pkt2 = Packet()
    pkt = Packet(20001, 20001, 0, 10, msg, 0x10)

    print(pkt.csum, ':', hex(pkt.csum))

    print(pkt)

    print(pkt.get_ack_bit())

    recv_data = pkt.pkt_pack()
    recv_data = b"".join([recv_data[0:len(recv_data)-1], b"\x00"])

    pkt2.pkt_unpack(recv_data)

    print(pkt2)

    print(pkt2.csum == pkt2.checksum())

    """ print(pkt)
 
    packed = pkt.pkt_pack()
    print(packed)

    new_pkt = Packet()
    print("New pkt before:", new_pkt)

    new_pkt.pkt_unpack(packed)
    print("New pkt unpacked:", new_pkt) """

    #unpacked = pkt.pkt_unpack(packed)
    # unpacked = struct.unpack('!H', packed)

    """ print(int.from_bytes(packed[0:2], byteorder='big', signed=False))
    print(packed[2:(len(packed)-2)])
    print(int.from_bytes(packed[(len(packed)-2):len(packed)], byteorder='big', signed=False)) """


    # print("Message:", new_pkt.data.decode())