import datetime
import logging
import os
import select
import socket
import sys
import time

from utils import send_arg_parser
from utils import init_send_socket

from packets import RECV_BUFFER, calculate_checksum
from packets import PacketGenerator, PacketExtractor, UnackedPacket

TIME_OUT     = 0.5 # sec
localhost    = socket.gethostbyname(socket.gethostname())
default_port = 8080

class Server(object):
      def __init__(self, send_ip=localhost, send_port=default_port,            \
                         recv_ip=localhost, recv_port=default_port+2,          \
                         filename="test/test.pdf",                             \
                         log_name="send_log.txt", window_size=1):
          self.send_addr   = (send_ip, send_port)
          self.server_sock = init_send_socket((send_ip, send_port))
          self.connections = [self.server_sock]
          self.recv_addr   = (recv_ip, recv_port)
          self.sent_file   = open(filename, "rb")
          self.log_file    = [sys.stdout, open(log_name, "w")]                 \
                             [log_name != "stdout"]
          self.file_size   = os.path.getsize(filename)

          self.window_size = window_size
          self.status      = None

          self.pkt_gen     = PacketGenerator(send_port, recv_port)
          self.pkt_ext     = PacketExtractor(send_port, recv_port)

          self.segment_count  = 0
          self.retrans_count  = 0

          self.send_time      = 0

          self.oldest_unacked_pkt = UnackedPacket()

          # logging module init
          self.logger = logging.getLogger("Server")
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
          print "====== Transfering Stats ======="
          print "Total bytes sent:", self.file_size
          print "Segments sent =", self.segment_count
          print "Segments Retranmitted =", self.retrans_count

      def send_file_response(self, *pkt_params):
          self.segment_counter()
          packet = self.pkt_gen.generate_packet(*pkt_params)
          self.logger.debug("checksum: %s" % calculate_checksum(*pkt_params))
          self.server_sock.sendto(packet, self.recv_addr)

      def send_initial_file_response(self):
          for i in xrange(self.window_size):
             seq_num = i * RECV_BUFFER
             ack_num = seq_num + self.window_size * RECV_BUFFER
             if i == 0:
                self.oldest_unacked_pkt.ack_num = ack_num
                self.oldest_unacked_pkt.begin_time = time.time()
             data_bytes = self.read_file_buffer(seq_num)
             fin_flag = len(data_bytes) == 0
             # if fin_flag:
             #    # means we already send all of data at initial stage,
             #    # dont need to tranfer the rest of packet.
             #    break
             self.send_file_response(seq_num, ack_num, fin_flag, data_bytes)
          self.send_time = time.time()

      def retransmit_file_response(self):
          self.logger.debug("retransmit!!!")
          self.logger.debug                                                    \
          ("oldest_unacked_pkt: %s" % self.oldest_unacked_pkt.ack_num)
          initial_seq =                                                        \
            self.oldest_unacked_pkt.ack_num - self.window_size * RECV_BUFFER
          for i in xrange(self.window_size):
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

      def is_oldest_unacked_pkt_timeout(self):
          if self.oldest_unacked_pkt.begin_time is None:
            return False
          return time.time() - self.oldest_unacked_pkt.begin_time >= TIME_OUT

      def server_loop(self):
          self.start_server()
          is_client_found = False
          estimated_rtt = 0
          print "start Pyle Transfer Server on %s with port %s ..."          \
                                        % self.send_addr
          while self.status:
                try:
                    if self.is_oldest_unacked_pkt_timeout():
                        self.logger.debug("timeout!")
                        self.retransmit_file_response()
                    read_sockets, write_sockets, error_sockets =               \
                                select.select(self.connections, [], [], 1)
                    if read_sockets:
                        recv_packet, recv_addr = self.server_sock.recvfrom     \
                                                                  (RECV_BUFFER)
                        if recv_packet == "I need a server~":
                            self.server_sock.sendto                            \
                                ("start file tranfer:%s:%s" %                  \
                                (self.window_size, self.file_size),            \
                                 recv_addr)
                            self.send_time = time.time()

                        elif recv_packet == "Come on!":
                            estimated_rtt = time.time() - self.send_time
                            is_client_found = True
                            self.send_initial_file_response()


                        elif is_client_found:
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
                            if recv_fin_flag:
                                log += " ACK FIN"
                                sample_rtt = time.time() - self.send_time
                                estimated_rtt = estimated_rtt * 0.875 + sample_rtt * 0.125
                                log += " " + str(estimated_rtt) + "\n"
                                self.log_file.write(log)
                                print "Delivery completed successfully"
                                self.print_transfer_stats()
                                self.close_server()
                            else:
                                log += " ACK"
                                if self.oldest_unacked_pkt.ack_num == recv_seq_num:
                                    sample_rtt = time.time() - self.send_time
                                    estimated_rtt = estimated_rtt * 0.875 + sample_rtt * 0.125
                                    log += " " + str(estimated_rtt) + "\n"
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
                                    estimated_rtt = estimated_rtt * 0.875 + sample_rtt * 0.125
                                    log += " " + str(estimated_rtt) + "\n"
                                    self.log_file.write(log)
                                    self.logger.debug("expected_ack not correct !!!")
                                    self.logger.debug("oldest_unacked_pkt.num: %s" % self.oldest_unacked_pkt.ack_num)
                                    self.logger.debug("recv_seq_num: %s, ignore" % recv_seq_num)
                                # else, ignore the packet

                except KeyboardInterrupt, SystemExit:
                       print "\nLeaving Pyle Transfer..."
                       self.close_server()

          self.server_sock.close()

      def start_server(self):
          self.status = True

      def close_server(self):
          self.sent_file.close()
          self.log_file.close()
          self.status = False

      def run(self):
          self.server_loop();

if __name__ == "__main__":
   params = send_arg_parser(sys.argv)
   server = Server(**params)
   server.run()