import os
import socket
import sys
import time

def init_recv_socket(address):
    recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_socket.bind(address)
    recv_socket.setblocking(True)
    return recv_socket

def init_send_socket(address):
    send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send_socket.bind(address)
    send_socket.setblocking(True)
    return send_socket

def progress_bar(process, filesize):
    progress = process * 50.0 / filesize
    sys.stdout.write("\rFile Transfering... [%-50s] %d%% \n" % ('-' * int(progress), 2 * progress))
    sys.stdout.flush()
    # time.sleep(0.1)
    if progress == 50:
        sys.stdout.write('\n')