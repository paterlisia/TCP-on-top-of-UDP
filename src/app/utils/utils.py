import socket
import sys

def init_recv_socket(address):
    recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_socket.bind(address)
    recv_socket.setblocking(True)
    return recv_socket

# init send socket: blocking
def init_socket(address):
    conn_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    conn_socket.bind(address)
    conn_socket.setblocking(True)
    return conn_socket

#--------function to visualize progress of current transform
def progress_bar(process, filesize):
    progress = process * 50.0 / filesize
    sys.stdout.write("\rFile Transfering... [%-50s] %d%% \n" % ('-' * int(progress), 2 * progress))
    sys.stdout.flush()
    if progress == 50:
        sys.stdout.write('\n')