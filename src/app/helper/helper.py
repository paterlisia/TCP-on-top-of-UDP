from packets.packet import PacketExtractor


class ProcessPacket(object):
    def __init__(self, recv_port, send_port):
        self.get_pkt = PacketExtractor(recv_port, send_port)

    # return info client and server needed : header and data
    def extract_info(self, recvd_pkt):
        header_params = self.get_pkt.get_header_params_from_packet(recvd_pkt)
        seq_num_from  = self.get_pkt.get_seq_num(header_params)
        ack_num_from  = self.get_pkt.get_ack_num(header_params)
        recv_fin_flag = self.get_pkt.get_fin_flag(header_params)
        recv_checksum = self.get_pkt.get_checksum(header_params)
        return header_params, seq_num_from, ack_num_from, recv_fin_flag, recv_checksum