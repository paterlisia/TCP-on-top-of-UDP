import datetime
import os
import socket
import sys
import time

def recv_arg_parser(argv):
    if len(argv) < 6:
       print "length of arguments is not enough."
       print "format: python Receiver.py <filename> <listening_port> <sender_IP> <sender_port> <log_filename>"
       print "ex. python Receiver.py test/received.txt 8082 192.168.0.3 8080 log/logfile.txt"
       sys.exit(1)
    else:
       return {
               "filename" : argv[1],                                           \
               "recv_port": int(argv[2]),                                      \
               "send_ip"  : argv[3],                                           \
               "send_port": int(argv[4]),                                      \
               "log_name" : argv[5]                                            \
              }

def send_arg_parser(argv):
    if len(argv) < 7:
       print "length of arguments is not enough."
       print "format: python Sender.py <filename> <remote_IP> <remote_port> <ack_port_num> <log_filename> <window_size>"
       print "ex. python Sender.py test/test.txt 192.168.0.3 41192 8082 log/logfile.txt 1000"
       sys.exit(1)
    else:
       return {
               "filename"    : argv[1],                                         \
               "recv_ip"     : argv[2],                                         \
               "recv_port"   : int(argv[3]),                                    \
               "send_port"   : int(argv[4]),                                    \
               "log_name"    : argv[5],                                         \
               "window_size" : int(argv[6])                                     \
              }

def init_recv_socket(address):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(address)
    udp_socket.setblocking(True)
    return udp_socket

def init_send_socket(address):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(address)
    udp_socket.setblocking(True)
    return udp_socket

def progress_bar(curr_filesize, filesize):
    progress = curr_filesize * 50.0 / filesize
    sys.stdout.write                                                           \
    ("\rFile Transfering... [%-50s] %d%%" % ('=' * int(progress), 2 * progress))
    sys.stdout.flush()
    time.sleep(0.1)
    if progress == 50:
        sys.stdout.write('\n')