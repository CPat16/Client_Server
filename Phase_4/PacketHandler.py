# This file contains the Packet class which handles packing functions
import struct

class Packet():
  def __init__(self, seq_num=-1, data=b''):
    self.seq_num = seq_num
    self.data = data
    if(seq_num >= 0):
      self.csum = self.checksum(self.seq_num, self.data)
    else:
      self.csum = -1
    self.fmt = '!H' + 'B'*len(self.data) + 'H'
  def __repr__(self):
    return "\nseq_num: {0}\n csum: {1}\n data: {2}\n".format(self.seq_num, self.csum, self.data)

  def pkt_pack(self):
    if isinstance(self.data, str):
      data = self.data.encode()
    else:
      data = self.data
    return struct.pack(self.fmt, self.seq_num, *data, self.csum)

  def pkt_unpack(self, packed):
    self.seq_num = int.from_bytes(packed[0:2], byteorder='big', signed=False)
    self.data = packed[2:(len(packed)-2)]
    self.csum = int.from_bytes(packed[(len(packed)-2):len(packed)], byteorder='big', signed=False)

  def carry_around_add(self, a, b):
    c = a + b
    # print(bin(c>>16))
    return (c & 0xffff) + (c >> 16)

  def checksum(self, seq, msg):
    csum = 0
    if isinstance(msg, str):
      msg = msg.encode()
    if isinstance(msg, (bytearray, bytes)):
      msg = int.from_bytes(msg, byteorder='big', signed=False)

    # add sequence number first
    csum = self.carry_around_add(csum, seq)

    #for _ in range(0, msg.bit_length()//16 + 1, 1):
    while msg != 0:
      next_bits = msg & 0xffff
      csum = self.carry_around_add(csum, next_bits)
      #print(csum, ':', bin(csum))
      msg = msg >> 16
      # print(bin(msg))
    return ~csum & 0xffff

if __name__ == "__main__":
  #msg = b'\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01'
  msg = "checksum2"
  # int_msg = int.from_bytes(msg, byteorder='big', signed=False)
  # print(bin(int_msg))

  pkt = Packet(0, msg)

  print(pkt.csum, ':', hex(pkt.csum))

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