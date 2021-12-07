import datetime
import logging
import os
import select
import socket
import sys
import time

# multi-threading for acks and pkts
from threading import Thread
from threading import ThreadError
# utils 
from utils.utils import init_send_socket

# handle error
from error.error import send_arg_parser

# packets
from packets.packet import RECV_BUFFER, calculate_checksum
from packets.packet import PacketGenerator, PacketExtractor, UnackedPacket

# params to set
TIME_OUT     = 0.5 # sec
localhost    = socket.gethostbyname(socket.gethostname())
default_port = 8080

class TcpClient(object):
    def __init__(self, send_ip=localhost, send_port=default_port,            \
                       recv_ip=localhost, recv_port=default_port+2,          \
                       filename="data/sendfile.txt",                             \
                       log_name="send_log.txt", window_size=1):
        # socket related variables
        self.send_addr   = (send_ip, send_port)
        self.tcp_client_sock = init_send_socket((send_ip, send_port))
        self.connections = [self.tcp_client_sock]
        self.recv_addr   = (recv_ip, recv_port)
        # file variables
        self.sent_file   = open(filename, "rb")
        self.log_file    = [sys.stdout, open(log_name, "w")]                 \
                           [log_name != "stdout"]
        self.file_size   = os.path.getsize(filename)
        # window size, acks, seq, timer
        self.window_size = window_size
        self.seq_num_to = 0
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.ack_num_to = 0
        self.estimated_rtt = 0
        self.status      = None
        self.pkt_gen     = PacketGenerator(send_port, recv_port)
        self.pkt_ext     = PacketExtractor(send_port, recv_port)
        self.segment_count  = 0
        self.retrans_count  = 0
        self.send_time      = 0
        self.oldest_unacked_pkt = UnackedPacket()
        # logging module init
        self.logger = logging.getLogger("TcpClient")
        self.logger.setLevel(logging.INFO)
        hd        = logging.StreamHandler()
        formatter = logging.                                                 \
                    Formatter                                                \
                    ("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        hd.setFormatter(formatter)
        self.logger.addHandler(hd)
    def retransmit_counter(self):
        self.retrans_count += 1
    def segment_counter(self):
        self.segment_count += 1
    def read_file_buffer(self, start_bytes):
        self.logger.debug("read file from %s byte" % start_bytes)
        self.sent_file.seek(start_bytes)
        data_bytes = self.sent_file.read(RECV_BUFFER)
        self.logger.debug("data_len: %s bytes" % len(data_bytes))
        return data_bytes
    def print_transfer_stats(self):
        print( "====== Transfering Stats =======")
        print ("Total bytes sent:", self.file_size)
        print ("Segments sent =", self.segment_count)
        print ("Segments Retranmitted =", self.retrans_count)
    def send_file_response(self, *pkt_params):
        self.segment_counter()
        packet = self.pkt_gen.generate_packet(*pkt_params)
        self.logger.debug("checksum: %s" % calculate_checksum(*pkt_params))
        a = self.tcp_client_sock.sendto(packet, self.recv_addr)
    def send_initial_file_response(self):
        for i in range(self.window_size):
            seq_num = i * RECV_BUFFER
            ack_num = seq_num + self.window_size * RECV_BUFFER
            # print(seq_num, ack_num)
            if i == 0:
                self.oldest_unacked_pkt.ack_num = ack_num
                self.oldest_unacked_pkt.begin_time = time.time()
            data_bytes = self.read_file_buffer(seq_num)
            fin_flag = len(data_bytes) == 0
            self.send_file_response(seq_num, ack_num, fin_flag, data_bytes)
        self.send_time = time.time()
    def retransmit_file_response(self):
        self.logger.debug("retransmit!!!")
        self.logger.debug                                                    \
        ("oldest_unacked_pkt: %s" % self.oldest_unacked_pkt.ack_num)
        initial_seq =                                                        \
          self.oldest_unacked_pkt.ack_num - self.window_size * RECV_BUFFER
        for i in range(self.window_size):
            self.retransmit_counter()
            seq_num = initial_seq + i * RECV_BUFFER
            self.logger.debug("retransmit_seq_num: %s" % seq_num)
            ack_num = seq_num + self.window_size * RECV_BUFFER
            self.logger.debug("retransmit_ack_num: %s" % ack_num)
            if i == 0:
                self.oldest_unacked_pkt.ack_num = ack_num
                self.oldest_unacked_pkt.begin_time = time.time()
            data_bytes = self.read_file_buffer(seq_num)
            fin_flag = len(data_bytes) == 0
            self.send_file_response(seq_num, ack_num, fin_flag, data_bytes)
        self.send_time = time.time()
      # function to judge time out
    def is_oldest_unacked_pkt_timeout(self):
        if self.oldest_unacked_pkt.begin_time is None:
            return False
        return time.time() - self.oldest_unacked_pkt.begin_time >= TIME_OUT
    # method to send packet
    def tcp_send_pkt(self):
        self.start_tcp_client()
        print ("start TcpClient on %s with port %s ..."% self.send_addr)
        while self.status:
            try:
                # self.seq_num_to += RECV_BUFFER
                data_bytes = self.read_file_buffer(self.seq_num_to)
                fin_flag = len(data_bytes) == 0
                self.send_file_response(self.seq_num_to, self.ack_num_to, fin_flag, data_bytes)
                self.send_time = time.time()
                self.seq_num_to += RECV_BUFFER
            except KeyboardInterrupt or SystemExit:
                print ("\nExit...bye")
                self.close_tcp_client()
        self.tcp_client_sock.close()

    # method to handle acks
    def tcp_valid_acks(self):
        print ("start acks on %s with port %s ..."% self.send_addr)
        while self.status:
            recv_packet, recv_addr = self.tcp_client_sock.recvfrom(RECV_BUFFER)
            header_params = self.pkt_ext.get_header_params_from_packet(recv_packet)
            self.seq_num_from  = self.pkt_ext                       \
                                .get_seq_num(header_params)
            self.ack_num_from  = self.pkt_ext                       \
                                .get_ack_num(header_params)
            recv_fin_flag = self.pkt_ext                       \
                                .get_fin_flag(header_params)
            log = str(datetime.datetime.now()) + " " +         \
                str(self.recv_addr[1]) + " " +               \
                str(self.send_addr[1]) + " " +               \
                str(self.seq_num_from) + " " +                    \
                str(self.ack_num_from)
            if recv_fin_flag:
                log += " ACK FIN"
                sample_rtt = time.time() - self.send_time
                self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                log += " " + str(self.estimated_rtt) + "\n"
                self.log_file.write(log)
                print ("Delivery completed successfully")
                self.print_transfer_stats()
                self.close_tcp_client()
            else:
                log += " ACK"
                if self.oldest_unacked_pkt.ack_num == self.seq_num_from:
                    sample_rtt = time.time() - self.send_time
                    self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                    log += " " + str(self.estimated_rtt) + "\n"
                    self.log_file.write(log)
                    seq_num  = self.ack_num_from    
                    ack_num  = self.seq_num_from                    \
                            + RECV_BUFFER * self.window_size
                    fin_flag = ack_num >= self.file_size
                    data_bytes = self.read_file_buffer(seq_num)
                    self.send_file_response                    \
                        (seq_num, ack_num, fin_flag, data_bytes)
                    self.oldest_unacked_pkt.ack_num += RECV_BUFFER
                    self.oldest_unacked_pkt.begin_time = time.time()
                else:
                    sample_rtt = time.time() - self.send_time
                    self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                    log += " " + str(self.estimated_rtt) + "\n"
                    self.log_file.write(log)
                    self.logger.debug("expected_ack not correct !!!")
                    self.logger.debug("oldest_unacked_pkt.num: %s" % self.oldest_unacked_pkt.ack_num)
                    self.logger.debug("recv_seq_num: %s, ignore" % self.seq_num_from)
    def tcp_client_loop(self):
        self.start_tcp_client()
        is_client_found = True
        self.estimated_rtt = 0
        print ("start TcpClient on %s with port %s ..."% self.send_addr)
        while self.status:
            try:
                # handle timeout situation: retransmission
                if self.is_oldest_unacked_pkt_timeout():
                    self.logger.debug("timeout!")
                    self.retransmit_file_response()
                # self.send_initial_file_response()
                read_sockets, write_sockets, error_sockets =               \
                            select.select(self.connections, [], [], 1)
                if read_sockets:
                    recv_packet, recv_addr = self.tcp_client_sock.recvfrom     \
                                                              (RECV_BUFFER)
                    # recv_packet = recv_packet.decode()
                    print(recv_packet)
                    # if recv_packet == "I need a tcp_client~".encode():
                    #     self.tcp_client_sock.sendto                            \
                    #         (("start file tranfer:%s:%s" %                  \
                    #         (self.window_size, self.file_size)).encode(),            \
                    #          recv_addr)
                    #     self.send_time = time.time()
                    # elif recv_packet == "Come on!".encode():
                    #     self.estimated_rtt = time.time() - self.send_time
                    #     is_client_found = True
                    #     self.send_initial_file_response()
                    if is_client_found:
                        header_params = self.pkt_ext                       \
                                            .get_header_params_from_packet \
                                                              (recv_packet)
                        recv_seq_num  = self.pkt_ext                       \
                                            .get_seq_num(header_params)
                        recv_ack_num  = self.pkt_ext                       \
                                            .get_ack_num(header_params)
                        recv_fin_flag = self.pkt_ext                       \
                                            .get_fin_flag(header_params)
                        log = str(datetime.datetime.now()) + " " +         \
                              str(self.recv_addr[1]) + " " +               \
                              str(self.send_addr[1]) + " " +               \
                              str(recv_seq_num) + " " +                    \
                              str(recv_ack_num)
                        print(log)
                        if recv_fin_flag:
                            log += " ACK FIN"
                            sample_rtt = time.time() - self.send_time
                            self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                            log += " " + str(self.estimated_rtt) + "\n"
                            self.log_file.write(log)
                            print ("Delivery completed successfully")
                            self.print_transfer_stats()
                            self.close_tcp_client()
                        else:
                            log += " ACK"
                            print(log)
                            if self.oldest_unacked_pkt.ack_num == recv_seq_num:
                                sample_rtt = time.time() - self.send_time
                                self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                                log += " " + str(self.estimated_rtt) + "\n"
                                self.log_file.write(log)
                                seq_num  = recv_ack_num
                                ack_num  = recv_seq_num                    \
                                           + RECV_BUFFER * self.window_size
                                fin_flag = ack_num >= self.file_size
                                data_bytes = self.read_file_buffer(seq_num)
                                self.send_file_response                    \
                                    (seq_num, ack_num, fin_flag, data_bytes)
                                self.oldest_unacked_pkt.ack_num += RECV_BUFFER
                                self.oldest_unacked_pkt.begin_time = time.time()
                            else:
                                sample_rtt = time.time() - self.send_time
                                self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                                log += " " + str(self.estimated_rtt) + "\n"
                                self.log_file.write(log)
                                self.logger.debug("expected_ack not correct !!!")
                                self.logger.debug("oldest_unacked_pkt.num: %s" % self.oldest_unacked_pkt.ack_num)
                                self.logger.debug("recv_seq_num: %s, ignore" % recv_seq_num)
                            # else, ignore the packet
                    else:
                        print('here')
            except KeyboardInterrupt or SystemExit:
                   print ("\nExit...bye")
                   self.close_tcp_client()
        self.tcp_client_sock.close()
    # status denote client start and close: start the client
    def start_tcp_client(self):
        self.status = True
        self.tcp_client_sock.sendto                            \
                            (("start file tranfer:%s:%s" %                  \
                            (self.window_size, self.file_size)).encode(),            \
                            self.recv_addr)
    # close tcp connection
    def close_tcp_client(self):
        self.sent_file.close()
        self.log_file.close()
        self.status = False
    def run(self):
        self.tcp_client_loop()
if __name__ == "__main__":
    params = send_arg_parser(sys.argv)
    # tcp_client = TcpClient(**params)
    # tcp_client.run()
    try:
        tcp_client = TcpClient(**params)
        client_th = Thread(target=tcp_client.tcp_send_pkt)
        client_th.setDaemon(True)
        client_th.start()

        ack_th = Thread(target=tcp_client.tcp_valid_acks)
        ack_th.setDaemon(True)
        ack_th.start()

    except ThreadError as e:
        print ('Fail to open thread. Error: #{0}, {1}'.format(str(e[0]), e[1]))
        sys.exit('Thread Fail')