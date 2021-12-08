# TCP on top of UDP

## A Python version realization
In this project, I implement sending and receiving transport-level code for implementing a simplified version of TCP, which
conducted on top of UDP. 

And for this project, I used `checksum`, computed over the TCP header and data (with the 
checksum set to zero); this does not quite correspond to the correct way of doing it (which includes parts of the IP header), 
but is close enough. Also, imported `ACK number` and `sequence number` to handle packets loss cases.

## screenshot


## Install and Run
- two ways of using this program
1. By terminal run python scripts
* **Note:  tested on macos platform

First, open ....., and input the operations in terminal
```bash
    $ cd your-project-path
```

And then start the tcpclient and tcpserver
```bash
    $ python tcpclient.py <listening_port> <address_for_acks> <port_for_acks>
    $ python tcpserver.py <address_of_udpl> <port_number_of_udpl> <windowsize> <ack_port_number>
```
Some explanations for args:
- tcpclient options arguments:
  - `listening_port`: The tcpclient receives data from.
  - `ip_address_for_acks`, `port_for_acks`:  writes it to the file and sends ACKs to.
- tcpclient options arguments:
    - ` ack_port_number`:  used to receive acknowledgements.

start newudpl:
```bash
./newudpl -i192.168.1.210:8080 -o192.168.1.210:8082 -B30000 -L50 -O30 -d0.6
```

- example: test on my computer(macos)
    - start newudpl
    ```bash
    ./newudpl -i192.168.1.210:8080 -o192.168.1.210:8082 -B30000 -L50 -O30 -d0.6
    ```
    - start tcpserver
    ```bash
        python tcpserver.py data/received.pdf 8082 192.168.1.210 8080 log/recv_log.txt
    ```
    - start tcpclient
    ```bash
        python tcpclient.py data/file.pdf 192.168.1.210 41192 8080 log/send_log.txt 1000
    ```

2. run the `start-client.sh` and `start-server.sh` file
    ```bash
    sh start-client.sh
    sh start-server.sh
    ```

## 

## project structure

## Maintainer
- [Jing Peng](https://github.com/paterlisia)