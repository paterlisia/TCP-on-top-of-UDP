
import os
import sys
import time
import socket
import logging
import datetime

# multi-threading for acks and pkts
from threading import Thread
from threading import Lock
from threading import ThreadError
# utils 
from utils.utils import init_send_socket

# handle error
from error.error import send_arg_parser

# packets
from helper.helper import ProcessPacket
from packets.packet import MSS, calculate_checksum
from packets.packet import PacketGenerator, PacketExtractor, UnackedPacket

# socket port, ip address
default_port = 8080
localhost = socket.gethostbyname(socket.gethostname())

class TcpClient(object):
    def __init__(self, send_ip=localhost, send_port=default_port, recv_ip=localhost, recv_port=default_port+2,          \
                       filename="data/sendfile.txt", log_name="send_log.txt", window_size=1):
        # socket related variables
        self.send_addr   = (send_ip, send_port)
        self.tcp_client_sock = init_send_socket((send_ip, send_port))
        self.connections = [self.tcp_client_sock]
        self.recv_addr   = (recv_ip, recv_port)
        # file variables
        self.sent_file   = open(filename, "rb")
        self.log_file    = [sys.stdout, open(log_name, "w")][log_name != "stdout"]
        self.file_size   = os.path.getsize(filename)
        # acks, seq, timer
        self.seq_num = 0
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.estimated_rtt = 0.5
        self.dev_rtt =0
        self.time_out_interval =0.5
        self.MAX_RANGE = 4294967296  # 2^32-1, which is used for avoiding overflow
        # lock to lock the shared variables
        self.header_lock = Lock()
        self.timer_lock = Lock()
        self.window_lock = Lock()
        # base, dup, window size, buffer
        self.buf = []
        self.base = 0
        self.dup_time = 0
        self.window_size = window_size
        # client status, file trans finish flag
        self.status      = None
        self.recv_fin_flag = False
        # helper object
        self.helper = ProcessPacket(recv_port, send_port)
        self.pkt_gen = PacketGenerator(send_port, recv_port)
        self.pkt_ext = PacketExtractor(send_port, recv_port)
        self.helper = ProcessPacket(recv_port, send_port)
        # count for segement sent times and retransmit times
        self.segment_count  = 0
        self.retrans_count  = 0
        self.is_timer = False
        self.send_time      = 0
        self.sample_rtt_pkt = (-1, -1) # (seq#, time)
        self.initial_packet = UnackedPacket()
        # logging module init
        self.logger = logging.getLogger("TcpClient")
        self.logger.setLevel(logging.INFO)
        hd = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        hd.setFormatter(formatter)
        self.logger.addHandler(hd)


    #----------read file--------------------------
    def read_bytes_from_file(self, start_bytes):
        if not self.recv_fin_flag:
            self.logger.debug("read file from %s byte" % start_bytes)
            self.sent_file.seek(start_bytes)
            data_bytes = self.sent_file.read(MSS)
            self.logger.debug("data_len: %s bytes" % len(data_bytes))
            return data_bytes
        return "".encode()

    # ----------send packet of file---------------
    def send_pkt(self, *pkt_params):
        self.segment_counter()
        packet = self.pkt_gen.generate_packet(*pkt_params)
        self.logger.debug("checksum: %s" % calculate_checksum(*pkt_params))
        try:
            a = self.tcp_client_sock.sendto(packet, self.recv_addr)
        except OSError:
            print("connection close, exit...")
            self.logger.debug("connection close")


    def send_init_packet(self):
        packet = self.pkt_gen.generate_packet(0, 0, 0, ("start file tranfer:%s:%s" %(self.window_size, self.file_size)).encode())
        print("send pkts, ", packet)
        self.tcp_client_sock.sendto(packet, self.recv_addr)
        if 0 not in self.buf:
            self.buf.append(0)
        # self.initial_packet.begin_time = time.time()
        # self.send_time = time.time()

    # -----------------handle on retransmiting the pkts --------------
    def retransmit_pkts(self):

        # ------------ 1. get the smallest seq # (also the ack recv from server) that is not acked to be transmitted----

        seq_num = self.base
        ack_num = self.base + MSS
        self.logger.debug("retransmit_seq_num: %s" % seq_num)
        data_bytes = self.read_bytes_from_file(seq_num)
        fin_flag = len(data_bytes) == 0

        # ------------2. retransmit the data ----------------

        self.send_pkt(seq_num, ack_num, fin_flag, data_bytes)

        # ------------ restart timer ------------------------
        self.restart_timer()
        # -----------3. clear sample rtt if retransmit the sample rtt seq-----------

        with self.timer_lock:
            if self.sample_rtt_pkt[0] == self.base:
                self.sample_rtt_pkt = (-1, -1)
        
        # count retransmit times
        self.retransmit_counter()


    # -----------------handle on time --------------------------------

    # *thread: handle timeout situation: retransmission
    def timer(self):
        print("start timer thread")
        while not self.recv_fin_flag:
            if self.handle_timeout():
                # handle on init pkt retransmit
                if not self.status:
                    self.send_init_packet()
                else:
                    print("Warnig: timeout, retransmit packet: ", self.base)
                    self.logger.debug("Warnig: timeout, retransmit packet: ", self.base)
                    self.retransmit_pkts()

    # function to compute estimate rtt
    def rtt_estimation(self):
        sample_rtt = time.time() - self.sample_rtt_pkt[1]
        print("sample rtt:", sample_rtt)
        self.estimated_rtt = self.estimated_rtt * 0.875 + sample_rtt * 0.125
        self.dev_rtt = 0.75 * sample_rtt + 0.25 * sample_rtt - self.estimated_rtt
        self.time_out_interval = self.estimated_rtt + 4 * self.dev_rtt

    # function to judge time out
    def handle_timeout(self):
        if not self.send_time:
            return False
        return time.time() - self.send_time >= self.time_out_interval

    # start timer
    def restart_timer(self):
        self.send_time = time.time()

    # set a timer
    def set_timer(self, status):
        self.is_timer = status


    #------------------TCP recv acks and send pkt threads------------
    # *thread: to recv acks from the server
    def tcp_recv_acks(self):
        print ("-------start TcpClient recv acks on %s with port %s ---"% self.send_addr)
        while not self.recv_fin_flag:
            #----------1. receive data from client--------------------------

            recv_packet, recv_addr = self.tcp_client_sock.recvfrom(MSS)
            print("client recv on %s with packet %s "% (self.recv_addr, recv_packet))
            with self.header_lock:
                header_params, self.seq_num_from, self.ack_num_from, self.recv_fin_flag, recv_checksum = self.helper.extract_info(recv_packet)
            print("packet header", header_params)
            log = str(datetime.datetime.now()) + " " +  str(self.recv_addr[1]) + " " +               \
                str(self.send_addr[1]) + " " +  str(self.seq_num_from) + " " +  str(self.ack_num_from)
                
            # handle on progress bar recv info, start send file after this ack
            if "got it".encode() in recv_packet:
                print("recv init pkt, start send pkts thread")
                self.status = True
            # ------2. recv fin_flag: record log, print conclusion, and close connection---------

            if self.recv_fin_flag:
                log += " ACK FIN"
                # self.rtt_estimation()
                log += " " + str(self.time_out_interval) + "\n"
                self.log_file.write(log)
                print ("File transmited successfully~")
                self.print_transfer_stats()
                self.close_tcp_client()

            # ------3. not finished----------------
            else:

                # -----3.1 receive duplicate acks

                if self.ack_num_from == self.base:
                    self.dup_time += 1
                    # self.rtt_estimation()
                    log += " " + str(self.time_out_interval) + "\n"
                    self.log_file.write(log)
                    # fast retransmit
                    if self.dup_time >= 3:
                        print("packet corrupted, retransmit packet")
                        self.retransmit_pkts()
                        self.dup_time = 0
                        self.logger.debug("expected_ack not correct, retransmit packet")
                        self.logger.debug("smallest unacked seq # %s" % self.initial_packet.ack_num)

                # ------3.2 receive ack value of self.ack_num_from---------------------------

                else:
                    # clear the duplicate times if received a different ack
                    self.dup_time = 0

                    # -----3.2.1 calculate sample rtt and update estimate rtt-----------------

                    with self.timer_lock:
                        # current sample rtt has been recorded
                        if self.sample_rtt_pkt[0] != -1:
                            # *receive ack for current sample rtt pkt, update estimate rtt
                            if self.ack_num_from == self.sample_rtt_pkt[0]:
                                self.rtt_estimation()
                            # reset sample rtt if did not get the right ack
                            self.sample_rtt_pkt = (-1, -1)
                    
                    # -----3.2.2 update buffer: pop all the pkts that have been acked

                    while self.buf and self.buf[0] <= self.ack_num_from:
                        print("remove seq %s from buf"%self.buf[0])
                        self.buf.pop()
                    
                    # -----3.2.3 update send base: update the smallest sent but not yet acked seq #

                    with self.window_lock:
                        self.base = self.ack_num_from
                        print("update send base with acks: ", self.ack_num_from)

                    #--------handle on timer: 1. restart timer if the ack != base(last ack loss) 2. stop timer otherwise
                    with self.timer_lock:
                        if self.base != self.seq_num:
                            self.restart_timer()
                        else:
                            self.set_timer(False)


    # *thread: to send pkts to tcpserver
    def tcp_send_pkts(self):
        print ("-------start TcpClient send pkts on %s with port %s ---"% self.send_addr)
        self.start_tcp_client()
        while not self.recv_fin_flag:
            while self.status:
                # ------send pkts in the sliding window range--------------------------
                while (self.seq_num + MSS) % self.MAX_RANGE <= (self.base + self.window_size) % self.MAX_RANGE \
                        and not self.recv_fin_flag:

                    # -------1. generate header: calculate seq, ack, and fin_flag ------

                    seq_num  = self.seq_num    
                    ack_num  = self.seq_num_from + MSS
                    # fin_flag = ack_num >= self.file_size
                    # read bytes from file
                    data_bytes = self.read_bytes_from_file(seq_num)
                    fin_flag = self.base == self.seq_num and len(data_bytes) == 0

                    # --------2. update sent but not yet acked seq # into buffer --------
                    self.buf.append(seq_num)
                    print("add seq # %s into buffer"%self.seq_num)

                    # --------3. send the pkt -----------------------------------------------
                    self.send_pkt(seq_num, ack_num, fin_flag, data_bytes)

    
                    # --------4. check if there is a timer has been started and update---

                    with self.timer_lock:
                        if self.sample_rtt_pkt[0] == -1:
                            self.sample_rtt_pkt = (self.seq_num, time.time())
                    
                    # --------start timer if there is no timer----------------------------
                        if not self.is_timer:
                            self.set_timer(True)
                            self.restart_timer()

                    # --------5. update seq_num-------------------------------------------
                    self.seq_num = (self.seq_num + MSS) % self.MAX_RANGE;


    # *thread: method to send packet
    def tcp_send_pkt(self):
        #----------send start client info to server---------------------
        self.start_tcp_client()
        print ("start TcpClient on %s with port %s ..."% self.send_addr)
        self.recv_fin_flag = False
        while self.status:
            try:
                #----------receive data from client--------------------------
                recv_packet, recv_addr = self.tcp_client_sock.recvfrom(MSS)
                print("client recv on %s with packet %s "% (self.recv_addr, recv_packet))
                header_params, self.seq_num_from, self.ack_num_from, self.recv_fin_flag, recv_checksum = self.helper.extract_info(recv_packet)
                print("packet header", header_params)
                log = str(datetime.datetime.now()) + " " +  str(self.recv_addr[1]) + " " +               \
                    str(self.send_addr[1]) + " " +  str(self.seq_num_from) + " " +  str(self.ack_num_from)
                #----------file transfer finished---------------------------------
                if self.recv_fin_flag:
                    log += " ACK FIN"
                    self.rtt_estimation()
                    log += " " + str(self.time_out_interval) + "\n"
                    self.log_file.write(log)
                    print ("Delivery completed successfully")
                    self.print_transfer_stats()
                    self.close_tcp_client()
                    self.send_pkt(self.ack_num_from, self.seq_num_from, self.recv_fin_flag, "".encode())
                else:
                    log += " ACK"
                    print(self.initial_packet.ack_num, self.seq_num_from)
                    # if self.initial_packet.ack_num == self.seq_num_from:
                    # range can be accepted without receiving acks
                    print("compare:", self.ack_num_from, self.base)
                    if self.base + self.window_size >= self.ack_num_from and self.base <= self.ack_num_from:
                        #  estimate rtt and update
                        self.rtt_estimation()
                        log += " " + str(self.time_out_interval) + "\n"
                        self.log_file.write(log)
                        # calculate seq # and ack # to send, and judge if the file finishes
                        seq_num  = self.ack_num_from    
                        ack_num  = self.seq_num_from + MSS
                        fin_flag = ack_num >= self.file_size
                        # read bytes fromm file
                        data_bytes = self.read_bytes_from_file(seq_num)
                        self.send_pkt(seq_num, ack_num, fin_flag, data_bytes)
                        # restart timer
                        self.restart_timer()
                        # push sent but unacked seq # into buf
                        if seq_num not in self.buf:
                            self.buf.append(seq_num)
                            print("buf now", self.buf)
                        print("send seq %s ack %s"%(seq_num, ack_num))
                        if self.base != self.seq_num_from:
                            self.buf.remove(self.seq_num_from)
                            print("remove acked %s seq from buf"%self.seq_num_from)
                        # update unACKed segment with smallest seq #
                        if self.base == self.seq_num_from:
                            self.base = self.buf[0] + MSS
                            self.buf.remove(self.seq_num_from)
                            print("remove acked %s seq from buf"%self.seq_num_from)
                            print(self.buf)
                            print("move window base to", self.base)
                            self.initial_packet.ack_num = ack_num
                            self.initial_packet.begin_time = time.time()
                    # received ACKs fall out of the window size range
                    else:
                        self.dup_time += 1
                        # self.rtt_estimation()
                        log += " " + str(self.time_out_interval) + "\n"
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
        # self.status = True
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
        client_th = Thread(target=tcp_client.tcp_send_pkts)
        client_th.start()
        # thread to rcv acks
        ack_th = Thread(target=tcp_client.tcp_recv_acks)
        ack_th.start()
        # thread to judge timeout event
        timer_th = Thread(target=tcp_client.timer)
        timer_th.start()
    except ThreadError as e:
        print ('Fail to open thread. Error: #{0}, {1}'.format(str(e[0]), e[1]))
        sys.exit('Thread Fail')
    except KeyboardInterrupt or SystemExit:
            print ("\nExit...bye")
            tcp_client.close_tcp_client()