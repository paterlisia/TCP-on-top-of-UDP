import struct

# ! means network packet, I means short int(2 bytes), H means int(4 bytes)
HEADER_FORMAT = "!HHIIHHHH"
head_len = 20
MSS   = 576
src_port = 0
dest_port = 1
seq_num   = 2
ack_num   = 3
fin_flag  = 4
window    = 5
checksum  = 6
urg   = 7

def checksum_calculator(src_port, dest_port, seq_num, ack_num, fin_flag, data_bytes):
    data_len = len(data_bytes)
    sum = 0
    #  add header field with data
    header_sum = src_port + dest_port + (seq_num >> 16) + (seq_num & 0xFFFF) + \
                     (ack_num >> 16) + (ack_num & 0xFFFF) + (fin_flag >> 16) + (fin_flag & 0xFFFF) + head_len
    sum += header_sum
    # Handle the case where the length is odd
    if (data_len & 1):
        data_len -= 1
        sum = data_bytes[data_len]
    else:
        sum = 0
    # Iterate through chars two by two and sum their byte values
    while data_len > 0:
        data_len -= 2
        sum += (data_bytes[data_len + 1]) << 8 + data_bytes[data_len]
    # Wrap overflow around
    sum = (sum >> 16) + (sum & 0xffff)
    result = (~ sum) & 0xffff  # One's complement
    result = result >> 8 | ((result & 0xff) << 8)  # Swap bytes
    return result

class Packet(object):
    def __init__(self):
        self.sorc_port = 0
        self.dest_port = 0

        self.seq_num  = 0
        self.ack_num  = 0

        self.fin_flag = 0
        self.window   = 0

        self.checksum = 0
        self.urg_ptr  = 0

class UnackedPacket(Packet):
    def __init__(self, ack_num=0, time_stamp=None):
        self.ack_num    = ack_num
        self.begin_time = time_stamp

class PacketExtractor(Packet):
    def __init__(self, sorc_port, dest_port):
        super(PacketExtractor, self).__init__()
        self.sorc_port = sorc_port
        self.dest_port = dest_port

    def get_data_from_packet(self, packet):
        return packet[head_len:]

    def get_header_params_from_packet(self, packet):
        return struct.unpack(HEADER_FORMAT, packet[:head_len])

    def get_seq_num(self, header_params):
        return header_params[seq_num]

    def get_ack_num(self, header_params):
        return header_params[ack_num]

    def get_fin_flag(self, header_params):
        return header_params[fin_flag]

    def get_checksum(self, header_params):
        return header_params[checksum]

    def is_checksum_valid(self, packet, recv_checksum):
        header_params = self.get_header_params_from_packet(packet)
        data_bytes = self.get_data_from_packet(packet)
        seq_num  = self.get_seq_num(header_params)
        ack_num  = self.get_ack_num(header_params)
        fin_flag = self.get_fin_flag(header_params)
        return checksum_calculator(self.sorc_port, self.dest_port, seq_num, ack_num, fin_flag, data_bytes) == recv_checksum


class PacketGenerator(Packet):
    def __init__(self, sorc_port, dest_port):
        super(PacketGenerator, self).__init__()
        self.sorc_port = sorc_port
        self.dest_port = dest_port

    def generate_tcp_header(self, seq_num, ack_num, fin_flag, user_data):
        self.ack_num  = ack_num
        self.seq_num  = seq_num
        self.fin_flag = fin_flag
        self.checksum = checksum_calculator(self.sorc_port, self.dest_port, seq_num, ack_num, fin_flag, user_data)
        tcp_header = struct.pack(HEADER_FORMAT, self.sorc_port, self.dest_port, self.seq_num, self.ack_num, self.fin_flag,                               \
                                self.window, self.checksum, self.urg_ptr )
        return tcp_header

    def generate_packet(self, seq_num, ack_num, fin_flag, user_data="".encode()):
        return self.generate_tcp_header(seq_num, ack_num, fin_flag, user_data) + user_data