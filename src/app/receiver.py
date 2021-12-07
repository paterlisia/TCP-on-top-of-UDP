# external library
import datetime
import logging
import os
import select
import socket
import sys

# utils function
from utils.utils import init_recv_socket, progress_bar

# handle error method
from error.error import recv_arg_parser

# make packets utils
from packets.packet import RECV_BUFFER, HEADER_LENGTH
from packets.packet import PacketGenerator, PacketExtractor

localhost = socket.gethostbyname(socket.gethostname())
default_port = 8080


class TcpServer(object):
    def __init__(self, recv_ip=localhost, recv_port=default_port+2,
                       send_ip=localhost, send_port=default_port,
                       filename="data/receivefile.txt",
                       log_name="data/recv_log.txt"):
        self.recv_sock = init_recv_socket((recv_ip, recv_port))
        self.connections = [self.recv_sock]
        self.recv_ip = recv_ip
        self.recv_port = recv_port
        self.window_size = 1
        self.file_size = 0
        self.send_addr = (send_ip, int(send_port))
        self.file_write = open(filename, "w")
        # acks, seq, timer
        self.seq_num_to = 0
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.ack_num_to = 0
        self.estimated_rtt = 0
        self.log_file = [sys.stdout, open(
            log_name, "w")][log_name != "stdout"]
        self.pkt_gen = PacketGenerator(recv_port, send_port)
        self.pkt_ext = PacketExtractor(recv_port, send_port)
        self.expected_ack = 0
        self.logger = logging.getLogger("TcpServer")
        self.logger.setLevel(logging.INFO)
        hd = logging.StreamHandler()
        formatter = logging.                                                 \
                    Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        hd.setFormatter(formatter)
        self.logger.addHandler(hd)

    def send_open_request(self):
        self.logger.debug("send open request")
        self.recv_sock.sendto("I need a tcp_client~".encode(), self.send_addr)
    def send_close_request(self, seq_num, ack_num, fin_flag):
        self.logger.info("Sending Close Request...")
        packet = self.pkt_gen.generate_packet(seq_num, ack_num, fin_flag)
        self.recv_sock.sendto(packet, self.send_addr)
    def write_file_buffer(self, start_bytes, data_bytes):
        self.logger.debug("write file from %s byte" % start_bytes)
        self.logger.debug("data_len: %s" % len(data_bytes))
        self.file_write.seek(start_bytes)
        print("write data: ", data_bytes)
        self.file_write.write(data_bytes)
    def is_write_file_completed(self):
        return os.path.getsize(self.file_write.name) == self.file_size
    def tcp_server_loop(self):
        self.start_tcp_server()
        print (("start tcp server on %s with port %s ...")% (self.recv_ip, self.recv_port))
        is_sender_found = True
        while self.status:
            try:
                if not is_sender_found:
                    self.send_open_request()
                # any of the descriptors in the sets are ready for read/write/exception conditions.
                read_sockets, write_sockets, error_sockets =               \
                           select.select(self.connections, [], [], 1)
                if read_sockets:
                    send_packet, send_addr = self.recv_sock.recvfrom       \
                                             (RECV_BUFFER + HEADER_LENGTH)
                    # print(send_packet)
                    if "start file tranfer".encode() in send_packet:
                        send_packet = send_packet.decode()
                        msg, self.window_size, self.file_size =            \
                                                    send_packet.split(':')
                        self.window_size = int(self.window_size)
                        is_sender_found  = True
                        self.file_size   = int(self.file_size)
                        self.logger.debug("window_size: %s" % self.window_size)
                        self.logger.debug("file_size: %s" % self.file_size)
                        self.send_addr   = send_addr
                        self.recv_sock.sendto("Come on!".encode(), self.send_addr)
                    else:
                        header_params = self.pkt_ext                       \
                                            .get_header_params_from_packet \
                                                               (send_packet)
                        recv_seq_num  = self.pkt_ext                       \
                                            .get_seq_num(header_params)
                        recv_ack_num  = self.pkt_ext                       \
                                            .get_ack_num(header_params)
                        recv_fin_flag = self.pkt_ext                       \
                                            .get_fin_flag(header_params)
                        send_checksum = self.pkt_ext.get_checksum(header_params)
                        log =   str(datetime.datetime.now()) + " " +       \
                                str(self.send_addr[1]) + " " +             \
                                str(self.recv_port) + " " +                \
                                str(recv_seq_num) + " " +                  \
                                str(recv_ack_num)
                        print(log)
                        if recv_fin_flag and self.is_write_file_completed():
                            print(recv_fin_flag)
                            self.log_file.write(log + " FIN\n")
                            send_data = self.pkt_ext                       \
                                            .get_data_from_packet          \
                                                      (send_packet)
                            self.write_file_buffer(recv_seq_num, send_data)
                            self.send_close_request                        \
                                 (recv_seq_num, recv_ack_num, recv_fin_flag)
                            self.close_tcp_server()
                            print ("Delivery completed successfully")
                        else:
                            # self.log_file.write(log + "\n")
                            print(self.expected_ack, recv_seq_num)
                            if self.expected_ack == recv_seq_num and       \
                               self.pkt_ext.is_checksum_valid(send_packet):
                                send_data = self.pkt_ext                   \
                                                .get_data_from_packet      \
                                                         (send_packet)
                                print(send_data)
                                self.write_file_buffer                     \
                                     (recv_seq_num, send_data)
                                progress_bar(os.path.getsize(self.file_write.name), self.file_size)
                                seq_num  = recv_ack_num
                                ack_num  = recv_seq_num                    \
                                           + RECV_BUFFER * self.window_size
                                self.logger.debug("seq_num: %s" % seq_num)
                                self.logger.debug("ack_num: %s" % ack_num)
                                fin_flag = 0
                                packet = self.pkt_gen                      \
                                             .generate_packet              \
                                             (seq_num, ack_num, fin_flag)
                                self.recv_sock.sendto(packet, self.send_addr)
                                self.expected_ack += RECV_BUFFER
                            else:
                                self.logger.debug("expected_ack not correct or packet corrupted")
                                self.logger.debug("expected_ack: %s" % self.expected_ack)
                                self.logger.debug("recv_seq_num: %s, ignore" % recv_seq_num)
            except KeyboardInterrupt or  SystemExit:
                 print ("\nExit...bye")
                 self.close_tcp_server()
                 os.remove(self.file_write.name)
        self.recv_sock.close()

    # tcp server 
    def tcp_recv_pkt(self):
        self.start_tcp_server()
        is_sender_found = False
        print (("start tcp server on %s with port %s ...")% (self.recv_ip, self.recv_port))
        while self.status:
            try:
                recvd_pkt, recvd_addr = self.recv_sock.recvfrom(RECV_BUFFER + HEADER_LENGTH)
                print("recv", recvd_pkt)
                header_params = self.pkt_ext                       \
                                    .get_header_params_from_packet \
                                                       (recvd_pkt)
                self.seq_num_from  = self.pkt_ext                       \
                                    .get_seq_num(header_params)
                self.ack_num_from  = self.pkt_ext                       \
                                    .get_ack_num(header_params)
                recv_fin_flag = self.pkt_ext                       \
                                    .get_fin_flag(header_params)
                send_checksum = self.pkt_ext.get_checksum(header_params)
                log =   str(datetime.datetime.now()) + " " +       \
                        str(self.send_addr[1]) + " " +             \
                        str(self.recv_port) + " " +                \
                        str(self.seq_num_from) + " " +                  \
                        str(self.ack_num_from)
                print(log)
                if recv_fin_flag and self.is_write_file_completed():
                    print(recv_fin_flag)
                    self.log_file.write(log + " FIN\n")
                    send_data = self.pkt_ext                       \
                                    .get_data_from_packet          \
                                              (recvd_pkt)
                    self.write_file_buffer(self.seq_num_from, send_data.decode())
                    self.send_close_request                        \
                         (self.seq_num_from, self.ack_num_from, recv_fin_flag)
                    self.close_tcp_server()
                    print ("Delivery completed successfully")
                else:
                    # self.log_file.write(log + "\n")
                    print(self.expected_ack, self.seq_num_from)
                    if self.expected_ack == self.seq_num_from and       \
                       self.pkt_ext.is_checksum_valid(recvd_pkt):
                        send_data = self.pkt_ext                   \
                                        .get_data_from_packet      \
                                                 (recvd_pkt)
                        print(send_data)
                        self.write_file_buffer                     \
                             (self.seq_num_from, send_data)
                        progress_bar(os.path.getsize(self.file_write.name), self.file_size)
                        seq_num  = self.ack_num_from
                        ack_num  = self.seq_num_from                    \
                                   + RECV_BUFFER * self.window_size
                        self.logger.debug("seq_num: %s" % seq_num)
                        self.logger.debug("ack_num: %s" % ack_num)
                        fin_flag = 0
                        packet = self.pkt_gen                      \
                                     .generate_packet              \
                                     (seq_num, ack_num, fin_flag)
                        self.recv_sock.sendto(packet, self.send_addr)
                        self.expected_ack += RECV_BUFFER
                    else:
                        self.logger.debug("expected_ack not correct or packet corrupted")
                        self.logger.debug("expected_ack: %s" % self.expected_ack)
                        self.logger.debug("recv_seq_num: %s, ignore" % self.seq_num_from)
            except KeyboardInterrupt or  SystemExit:
                 print ("\nExit...bye")
                 self.close_tcp_server()
                 os.remove(self.file_write.name)
        self.recv_sock.close()
    def start_tcp_server(self):
        self.status = True
    def close_tcp_server(self):
        self.file_write.close()
        self.log_file.close()
        self.status = False
    def run(self):
        self.tcp_server_loop()  
if __name__ == "__main__":
   params = recv_arg_parser(sys.argv)
   tcp_server = TcpServer(**params)
   tcp_server.tcp_recv_pkt()