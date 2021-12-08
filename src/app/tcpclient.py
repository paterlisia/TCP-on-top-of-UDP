import datetime
import logging
import os
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
from helper.helper import ProcessPacket
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
        # acks, seq, timer
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.estimated_rtt = 0.5
        # base, dup, window size, buffer
        self.base = 0
        self.window_size = window_size
        self.dup_time = 0
        self.buf = []
        # client status, file trans finish flag
        self.status      = None
        self.recv_fin_flag = False
        self.pkt_gen     = PacketGenerator(send_port, recv_port)
        self.pkt_ext     = PacketExtractor(send_port, recv_port)
        # helper object
        self.helper = ProcessPacket(recv_port, send_port)
        self.segment_count  = 0
        self.retrans_count  = 0
        self.send_time      = 0
        self.initial_packet = UnackedPacket()
        # logging module init
        self.logger = logging.getLogger("TcpClient")
        self.logger.setLevel(logging.INFO)
        hd        = logging.StreamHandler()
        formatter = logging.                                                 \
                    Formatter                                                \
                    ("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        hd.setFormatter(formatter)
        self.logger.addHandler(hd)


    #----------read file--------------------------
    def read_file_buffer(self, start_bytes):
        self.logger.debug("read file from %s byte" % start_bytes)
        self.sent_file.seek(start_bytes)
        data_bytes = self.sent_file.read(RECV_BUFFER)
        self.logger.debug("data_len: %s bytes" % len(data_bytes))
        return data_bytes

    # ----------send packet of file---------------
    def send_pkt(self, *pkt_params):
        self.segment_counter()
        packet = self.pkt_gen.generate_packet(*pkt_params)
        self.logger.debug("checksum: %s" % calculate_checksum(*pkt_params))
        a = self.tcp_client_sock.sendto(packet, self.recv_addr)
        # push unacked seq # into buf
        self.buf.append(pkt_params[0])
        self.send_time = time.time()


    #----------retransmit the file --------------------------
    def retransmit_pkt(self):
        self.logger.debug("retransmit!!!")
        print ("oldest_unacked_pkt: %s" % self.initial_packet.ack_num)
        if self.initial_packet.ack_num != 0:
            # initial_seq =  self.initial_packet.ack_num - self.window_size * RECV_BUFFER
            print("initial", self.base)
            for i in range(self.window_size):
                self.retransmit_counter()
                seq_num = self.base + i * RECV_BUFFER
                self.logger.debug("retransmit_seq_num: %s" % seq_num)
                ack_num = seq_num + self.window_size * RECV_BUFFER
                self.logger.debug("retransmit_ack_num: %s" % ack_num)
                if i == 0:
                    self.initial_packet.ack_num = ack_num
                    self.initial_packet.begin_time = time.time()
                data_bytes = self.read_file_buffer(seq_num)
                fin_flag = len(data_bytes) == 0
                self.send_pkt(seq_num, ack_num, fin_flag, data_bytes)
        else :
            print("retransmit the start file info")
            self.send_init_packet()
        self.send_time = time.time()

    # -----------------handle on time --------------------------------

    # handle timeout situation: retransmission
    def timer(self):
        print("start timer thread")
        while self.status:
            try:
                if self.handle_timeout():
                    print("Warnig: timeout, retransmit packet: ", self.initial_packet.ack_num)
                    self.retransmit_pkt()
            except KeyboardInterrupt or SystemExit:
                print ("\nExit...bye")

    # function to estimate rtt
    def rtt_estimation(self):
        sample_rtt = time.time() - self.send_time
        self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125

    # function to judge time out
    def handle_timeout(self):
        if self.initial_packet.begin_time is None:
            return False
        return time.time() - self.initial_packet.begin_time >= self.estimated_rtt


    def send_init_packet(self):
        packet = self.pkt_gen.generate_packet(0, 0, 0, \
                            ("start file tranfer:%s:%s" %(self.window_size, self.file_size)).encode())
        self.tcp_client_sock.sendto(packet, self.recv_addr)
        self.buf.append(0)
        self.initial_packet.begin_time = time.time()
        self.send_time = time.time()


    # method to send packet
    def tcp_send_pkt(self):
        #----------send start client info to server---------------------
        self.start_tcp_client()
        print ("start TcpClient on %s with port %s ..."% self.send_addr)
        self.recv_fin_flag = False
        while self.status:
            try:
                #----------receive data from client--------------------------
                recv_packet, recv_addr = self.tcp_client_sock.recvfrom(RECV_BUFFER)
                print("client recv on %s with packet %s "% (self.recv_addr, recv_packet))
                header_params, self.seq_num_from, self.ack_num_from, self.recv_fin_flag, recv_checksum = self.helper.extract_info(recv_packet)
                print("packet header", header_params)
                log = str(datetime.datetime.now()) + " " +         \
                    str(self.recv_addr[1]) + " " +               \
                    str(self.send_addr[1]) + " " +               \
                    str(self.seq_num_from) + " " +                    \
                    str(self.ack_num_from)
                #----------file transfer finished--------------------------
                if self.recv_fin_flag:
                    log += " ACK FIN"
                    self.rtt_estimation()
                    log += " " + str(self.estimated_rtt) + "\n"
                    self.log_file.write(log)
                    print ("Delivery completed successfully")
                    self.print_transfer_stats()
                    self.close_tcp_client()
                else:
                    log += " ACK"
                    print(self.initial_packet.ack_num, self.seq_num_from)
                    # if self.initial_packet.ack_num == self.seq_num_from:
                    # range can be accepted without receiving acks
                    if self.base + self.window_size >= self.ack_num_from and self.base >= self.ack_num_from:
                        #  estimate rtt and update
                        self.rtt_estimation()
                        log += " " + str(self.estimated_rtt) + "\n"
                        self.log_file.write(log)
                        # calculate seq # and ack # to send, and judge if
                        seq_num  = self.ack_num_from    
                        ack_num  = self.seq_num_from + RECV_BUFFER
                        fin_flag = ack_num >= self.file_size
                        data_bytes = self.read_file_buffer(seq_num)
                        self.send_pkt (seq_num, ack_num, fin_flag, data_bytes)
                        print("send seq %s ack %s"%(seq_num, ack_num))
                        self.buf.remove(self.seq_num_from)
                        # update unACKed segment with smallest seq #
                        if self.base == self.seq_num_from:
                            self.base = self.buf[0]
                            self.initial_packet.ack_num = ack_num
                            self.initial_packet.begin_time = time.time()
                    # received ACKs fall out of the window size range
                    else:
                        self.dup_time += 1
                        self.rtt_estimation()
                        log += " " + str(self.estimated_rtt) + "\n"
                        self.log_file.write(log)
                        # fast retransmit
                        if self.dup_time >= 3:
                            print("packet corrupted, retransmit packet")
                            self.retransmit_pkt()
                            self.dup_time = 0
                            self.logger.debug("expected_ack not correct !!!")
                            self.logger.debug("oldest_unacked_pkt.num: %s" % self.initial_packet.ack_num)
                            self.logger.debug("recv_seq_num: %s, ignore" % self.seq_num_from)
            except KeyboardInterrupt or SystemExit:
                print ("\nExit...bye")
                self.close_tcp_client()
        self.tcp_client_sock.close()


    # -----------TCP start and close----------------
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

    # ----------transfer info conclusion part-----------
    def print_transfer_stats(self):
        print( "---------Transmission results-----------")
        print ("Total bytes sent:", self.file_size)
        print ("Segments sent =", self.segment_count)
        print ("Segments Retranmitted =", self.retrans_count)

    # count for retransmission
    def retransmit_counter(self):
        self.retrans_count += 1

    # count for segment sent
    def segment_counter(self):
        self.segment_count += 1


if __name__ == "__main__":
    params = send_arg_parser(sys.argv)
    try:
        tcp_client = TcpClient(**params)
        # thread for handling tcp send pkt
        client_th = Thread(target=tcp_client.tcp_send_pkt)
        client_th.start()
        # thread to judge timeout event
        ack_th = Thread(target=tcp_client.timer)
        ack_th.start()
    except ThreadError as e:
        print ('Fail to open thread. Error: #{0}, {1}'.format(str(e[0]), e[1]))
        sys.exit('Thread Fail')