import datetime
import os
import socket
import sys
import time

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