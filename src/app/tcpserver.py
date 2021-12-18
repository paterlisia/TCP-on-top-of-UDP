# external library
import datetime
import logging
import os
import socket
import sys

# utils function
from utils.utils import init_socket, progress_bar

# handle error method
from error.error import recv_arg_parser

# make packets utils
from helper.helper import ProcessPacket
from packets.packet import MSS, head_len
from packets.packet import PacketGenerator, PacketExtractor
from helper.helper import ProcessPacket

localhost = socket.gethostbyname(socket.gethostname())
default_port = 8080


class TcpServer(object):
    def __init__(self, recv_ip=localhost, recv_port=default_port+2,
                       send_ip=localhost, send_port=default_port,
                       filename="data/receivefile.txt",
                       log_name="data/recv_log.txt"):
        self.recv_sock = init_socket((recv_ip, recv_port))
        self.connections = [self.recv_sock]
        self.recv_ip = recv_ip
        self.recv_port = recv_port
        self.file_size = 0
        self.send_addr = (send_ip, int(send_port))
        self.file_write = open(filename, "w")
        # helper object
        self.helper = ProcessPacket(recv_port, send_port)
        # acks, seq, timer
        self.seq_num_to = 0
        self.seq_num_from = 0
        self.ack_num_from = 0
        self.ack_num_to = 0
        self.estimated_rtt = 0
        self.recv_fin_flag = 0
        # buffer
        self.buf = {}
        self.log_file = [sys.stdout, open(
            log_name, "w")][log_name != "stdout"]
        self.pkt_gen = PacketGenerator(recv_port, send_port)
        self.pkt_ext = PacketExtractor(recv_port, send_port)
        # helper object
        self.helper = ProcessPacket(recv_port, send_port)
        self.expected_seq = 0
        self.logger = logging.getLogger("TcpServer")
        self.logger.setLevel(logging.INFO)
        hd = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        hd.setFormatter(formatter)
        self.logger.addHandler(hd)


    def send_close_request(self, seq_num, ack_num, fin_flag):
        self.logger.info("Sending Close Request...")
        packet = self.pkt_gen.generate_packet(seq_num, ack_num, fin_flag)
        self.recv_sock.sendto(packet, self.send_addr)


    def write_file_buffer(self, start_bytes, data_bytes):
        self.logger.debug("write file from %s byte" % start_bytes)
        self.logger.debug("data_len: %s" % len(data_bytes))
        self.file_write.seek(start_bytes)
        self.file_write.write(data_bytes)


    def is_write_file_completed(self):
        return os.path.getsize(self.file_write.name) == self.file_size


    # send ack for current packet
    def tcp_send_ack(self):
        fin_flag = 0
        packet = self.pkt_gen                      \
                    .generate_packet              \
                    (self.ack_num_from, self.seq_num_from, fin_flag)
        self.recv_sock.sendto(packet, self.send_addr)


    # tcp server 
    def tcp_recv_pkt(self):
        self.start_tcp_server()
        print (("start tcp server on %s with port %s ...")% (self.recv_ip, self.recv_port))
        while self.status:
            try:
                # -------------- receive pkt from tcpclient---------------------
                recvd_pkt, recvd_addr = self.recv_sock.recvfrom(MSS + head_len)
                # print("recv on port %s with packet %s"%(self.recv_port, recvd_pkt))
                # extract params from packet
                header_params, self.seq_num_from, self.ack_num_from, self.recv_fin_flag, recv_checksum = self.helper.extract_info(recvd_pkt)
                print("header params", header_params)
                print("recv packet with seq %s with ack %s"%(self.seq_num_from, self.ack_num_from))
                log =   str(datetime.datetime.now()) + " " + str(self.send_addr[1]) + " " +             \
                        str(self.recv_port) + " " +  str(self.seq_num_from) + " " +  str(self.ack_num_from)
                if not self.pkt_ext.is_checksum_valid(recvd_pkt, recv_checksum):
                    print("checksum not right, dismiss packet")
                    # ack the previous packet
                    packet = self.pkt_gen.generate_packet(self.seq_num_to, self.ack_num_to, 0)
                    self.recv_sock.sendto(packet, self.send_addr)
                else:
                    # get the filesize for progress bar
                    if "start file tranfer".encode() in recvd_pkt:
                        send_packet = self.pkt_ext.get_data_from_packet(recvd_pkt).decode()
                        msg, window_size, self.file_size = send_packet.split(':')
                        self.file_size   = int(self.file_size)
                        self.logger.debug("file_size: %s" % self.file_size)
                        seq_num  = self.ack_num_from
                        ack_num  = self.seq_num_from + MSS  # seq number of next byte expected from the client
                        print("acks", self.seq_num_from)
                        fin_flag = 0
                        packet = self.pkt_gen.generate_packet(0, 0, fin_flag, "got it".encode())
                        self.recv_sock.sendto(packet, self.send_addr)
                        print("send seq %s ack %s"%(seq_num, ack_num))
                    else:

                        #------------1. check checksum, resend if checksum is not right-----------------

                        if not self.pkt_ext.is_checksum_valid(recvd_pkt, recv_checksum):
                            print("packet corrupted, checksum does not confirm, retransmit")
                            packet = self.pkt_gen.generate_packet(self.seq_num_to, self.ack_num_to, 0)
                            self.recv_sock.sendto(packet, self.send_addr)
                            # packet inordered, retransmit
                            self.recv_fin_flag = 0
                        
                        #-----------2. check is the file has been fully transmitted---------------
                        if self.recv_fin_flag:
                            self.log_file.write(log + " FIN\n")
                            send_data = self.pkt_ext.get_data_from_packet(recvd_pkt)
                            self.write_file_buffer(self.seq_num_from, send_data.decode())
                            self.send_close_request                        \
                                (self.seq_num_from, self.ack_num_from, self.recv_fin_flag)
                            self.close_tcp_server()
                            print ("File transmited successfully~")
                        else:
                            self.log_file.write(log + "\n")
                            print("expected ack %s, ack received %s" %(self.expected_seq, self.seq_num_from))
                            send_data = self.pkt_ext.get_data_from_packet(recvd_pkt).decode()
                            
                            # ---------3. check seq number, if seq # = expected, send culmalative ack--------------------
                            if self.expected_seq == self.seq_num_from:

                            # ---------3.1 extract data from pkt and record file--------------------
                                self.write_file_buffer(self.seq_num_from, send_data)
                                progress_bar(os.path.getsize(self.file_write.name), self.file_size)

                            # ---------3.2 update seq_num and ack_num--------------------

                                seq_num  = self.ack_num_from
                                ack_num  = self.seq_num_from + MSS
                                self.logger.debug("seq_num: %s" % seq_num)
                                self.logger.debug("ack_num: %s" % ack_num)
                                print("send seq %s ack %s"%(seq_num, ack_num))

                            # ---------3.3 update expected seq number--------------------

                                self.ack_num_to = self.seq_num_from + MSS
                                self.seq_num_to = self.ack_num_from
                                self.expected_seq += MSS

                            # ---------3.4 update expected seq number if arriving seg fills in gap---------

                                while self.expected_seq in self.buf:
                             # -----3.4.1 write data into file---------------------------------------
                                    self.write_file_buffer(self.expected_seq, self.buf[self.expected_seq])
                                    print("write data from buf: ", self.expected_seq)
                             # -----3.4.2 remove written data seq in buf-----------------------------
                                    del self.buf[self.expected_seq]
                                    self.expected_seq += MSS
                                    
                            # ---------3.5 send ack with the new start of the smallest seq number in buffer---------
                                
                                packet = self.pkt_gen.generate_packet(seq_num, self.expected_seq, self.recv_fin_flag)
                                self.recv_sock.sendto(packet, self.send_addr)
                            # ---------3. arrival of out-of-order seg with higher than expected seq #-------
                            else:
                                # ---------3.1 push into buffer with (seq # , data_str)-----------------

                                self.buf[self.seq_num_from] = send_data
                                print("push seq num %s to buf"%self.seq_num_from)

                                # ---------3.2 send duplicate ack, ack the previous packet----------------

                                packet = self.pkt_gen.generate_packet(self.seq_num_to, self.expected_seq, 0)
                                self.recv_sock.sendto(packet, self.send_addr)
                                print("send duplicate with ack ", self.expected_seq)
                                self.logger.debug("expected_seq not correct or packet corrupted")
                                self.logger.debug("expected_seq: %s" % self.expected_seq)
                                self.logger.debug("recv_seq_num: %s, ignore" % self.seq_num_from)
            except KeyboardInterrupt or  SystemExit:
                 print ("\nExit...bye")
                 self.close_tcp_server()
                 os.remove(self.file_write.name)
        self.recv_sock.close()

# -----------TCP start and close----------------
    def start_tcp_server(self):
        self.status = True


    def close_tcp_server(self):
        self.file_write.close()
        self.log_file.close()
        self.status = False


if __name__ == "__main__":
   params = recv_arg_parser(sys.argv)
   tcp_server = TcpServer(**params)
   tcp_server.tcp_recv_pkt()