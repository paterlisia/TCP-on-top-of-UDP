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
# TIME_OUT     = 0.5 # sec
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
        # window size, acks, seq, timer, dup
        self.window_size = window_size
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.estimated_rtt = 0.5
        self.dup_time = 0
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
    #----------read file--------------------------
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
        self.send_time = time.time()
    #----------retransmit the file --------------------------
    def retransmit_file_response(self):
        self.logger.debug("retransmit!!!")
        print ("oldest_unacked_pkt: %s" % self.oldest_unacked_pkt.ack_num)
        if self.oldest_unacked_pkt.ack_num != 0:
            initial_seq =  self.oldest_unacked_pkt.ack_num - self.window_size * RECV_BUFFER
            print("initial", initial_seq)
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
        else :
            print("retransmit the start file info")
            self.send_init_packet()
        self.send_time = time.time()
      # function to judge time out
    def is_oldest_unacked_pkt_timeout(self):
        if self.oldest_unacked_pkt.begin_time is None:
            return False
        return time.time() - self.oldest_unacked_pkt.begin_time >= self.estimated_rtt
    # handle timeout situation: retransmission
    def timer(self):
        print("start timer thread")
        while self.status:
            if self.is_oldest_unacked_pkt_timeout():
                print("Warnig: timeout, retransmit packet: ", self.oldest_unacked_pkt.ack_num)
                self.retransmit_file_response()

    def send_init_packet(self):
        packet = self.pkt_gen.generate_packet(0, 0, 0, \
                            ("start file tranfer:%s:%s" %(self.window_size, self.file_size)).encode())
        self.tcp_client_sock.sendto(packet, self.recv_addr)
        self.oldest_unacked_pkt.begin_time = time.time()
        self.send_time = time.time()
    # method to send packet
    def tcp_send_pkt(self):
        #----------send start client info to server---------------------
        self.start_tcp_client()
        print ("start TcpClient on %s with port %s ..."% self.send_addr)
        recv_fin_flag = False
        while self.status:
            try:
                #----------receive data from client--------------------------
                recv_packet, recv_addr = self.tcp_client_sock.recvfrom(RECV_BUFFER)
                print("client recv on %s with packet %s "% (self.recv_addr, recv_packet))
                header_params = self.pkt_ext.get_header_params_from_packet(recv_packet)
                self.seq_num_from  = self.pkt_ext                       \
                                    .get_seq_num(header_params)
                self.ack_num_from  = self.pkt_ext                       \
                                    .get_ack_num(header_params)
                recv_fin_flag = self.pkt_ext                       \
                                    .get_fin_flag(header_params)
                print("packet header", header_params)
                log = str(datetime.datetime.now()) + " " +         \
                    str(self.recv_addr[1]) + " " +               \
                    str(self.send_addr[1]) + " " +               \
                    str(self.seq_num_from) + " " +                    \
                    str(self.ack_num_from)
                #----------file transfer finished--------------------------
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
                    print(self.oldest_unacked_pkt.ack_num, self.seq_num_from)
                    if self.oldest_unacked_pkt.ack_num == self.seq_num_from:
                        sample_rtt = time.time() - self.send_time
                        self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                        log += " " + str(self.estimated_rtt) + "\n"
                        self.log_file.write(log)
                        seq_num  = self.ack_num_from    
                        ack_num  = self.seq_num_from                    \
                                + RECV_BUFFER
                        fin_flag = ack_num >= self.file_size
                        data_bytes = self.read_file_buffer(seq_num)
                        self.send_file_response                    \
                            (seq_num, ack_num, fin_flag, data_bytes)
                        print("send seq %s ack %s"%(seq_num, ack_num))
                        self.oldest_unacked_pkt.ack_num = ack_num
                        self.oldest_unacked_pkt.begin_time = time.time()
                    else:
                        sample_rtt = time.time() - self.send_time
                        self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
                        log += " " + str(self.estimated_rtt) + "\n"
                        self.log_file.write(log)
                        print("packet corrupted, retransmit packet")
                        self.retransmit_file_response()
                        self.logger.debug("expected_ack not correct !!!")
                        self.logger.debug("oldest_unacked_pkt.num: %s" % self.oldest_unacked_pkt.ack_num)
                        self.logger.debug("recv_seq_num: %s, ignore" % self.seq_num_from)
            except KeyboardInterrupt or SystemExit:
                print ("\nExit...bye")
                self.close_tcp_client()
        self.tcp_client_sock.close()

    def start_tcp_client(self):
        self.status = True
        self.send_init_packet()
    # close tcp connection
    def close_tcp_client(self):
        self.sent_file.close()
        self.log_file.close()
        self.status = False
    def run(self):
        self.tcp_send_pkt()
if __name__ == "__main__":
    params = send_arg_parser(sys.argv)
    try:
        tcp_client = TcpClient(**params)

        client_th = Thread(target=tcp_client.tcp_send_pkt)
        client_th.start()

        ack_th = Thread(target=tcp_client.timer)
        ack_th.start()
    except ThreadError as e:
        print ('Fail to open thread. Error: #{0}, {1}'.format(str(e[0]), e[1]))
        sys.exit('Thread Fail')