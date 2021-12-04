import struct

# ! means network packet, I means short int(2 bytes), H means int(4 bytes)
HEADER_FORMAT = "!HHIIHHHH"
HEADER_LENGTH = 20
RECV_BUFFER   = 576
SORC_PORT_POS = 0
DEST_PORT_POS = 1
SEQ_NUM_POS   = 2
ACK_NUM_POS   = 3
FIN_FLAG_POS  = 4
WINDOW_POS    = 5
CHECKSUM_POS  = 6
URG_PTR_POS   = 7

def calculate_checksum(seq_num, ack_num, fin_flag, data_bytes):
    data_len = len(data_bytes)
    # Handle the case where the length is odd
    if (data_len & 1):
        data_len -= 1
        sum = ord(data_bytes[data_len])
    else:
        sum = 0
    # Iterate through chars two by two and sum their byte values
    while data_len > 0:
        data_len -= 2
        sum += (ord(data_bytes[data_len + 1]) << 8) + ord(data_bytes[data_len])
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
    def __init__(self, ack_num=None, time_stamp=None):
        self.ack_num    = ack_num
        self.begin_time = time_stamp

class PacketExtractor(Packet):
    def __init__(self, sorc_port, dest_port):
        super(PacketExtractor, self).__init__()
        self.sorc_port = sorc_port
        self.dest_port = dest_port

    def get_data_from_packet(self, packet):
        return packet[HEADER_LENGTH:]

    def get_header_params_from_packet(self, packet):
        return struct.unpack(HEADER_FORMAT, packet[:HEADER_LENGTH])

    def get_seq_num(self, header_params):
        return header_params[SEQ_NUM_POS]

    def get_ack_num(self, header_params):
        return header_params[ACK_NUM_POS]

    def get_fin_flag(self, header_params):
        return header_params[FIN_FLAG_POS]

    def get_checksum(self, header_params):
        return header_params[CHECKSUM_POS]

    def is_checksum_valid(self, packet):
        header_params = self.get_header_params_from_packet(packet)
        data_bytes    = self.get_data_from_packet(packet)
        seq_num  = self.get_seq_num(header_params)
        ack_num  = self.get_ack_num(header_params)
        fin_flag = self.get_fin_flag(header_params)
        header_checksum = self.get_checksum(header_params)
        return calculate_checksum(seq_num, ack_num, fin_flag, data_bytes) == header_checksum


class PacketGenerator(Packet):
    def __init__(self, sorc_port, dest_port):
        super(PacketGenerator, self).__init__()
        self.sorc_port = sorc_port
        self.dest_port = dest_port

    def generate_tcp_header(self, seq_num, ack_num, fin_flag, user_data):
        self.ack_num  = ack_num
        self.seq_num  = seq_num
        self.fin_flag = fin_flag
        self.checksum = calculate_checksum(seq_num, ack_num, fin_flag, user_data)
        tcp_header = struct.pack(                                             \
                                 HEADER_FORMAT,                               \
                                 self.sorc_port,                              \
                                 self.dest_port,                              \
                                 self.seq_num,                                \
                                 self.ack_num,                                \
                                 self.fin_flag,                               \
                                 self.window,                                 \
                                 self.checksum,                               \
                                 self.urg_ptr                                 \
                                )
        return tcp_header

    def generate_packet(self, seq_num, ack_num, fin_flag, user_data=""):
        return self.generate_tcp_header(seq_num, ack_num, fin_flag, user_data)\
               + user_data