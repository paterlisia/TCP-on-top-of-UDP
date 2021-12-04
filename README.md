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

And then start the server and client
```bash
    $ python server.py <listening_port> <address_for_acks> <port_for_acks>
    $ python client.py <address_of_udpl> <port_number_of_udpl> <windowsize> <ack_port_number>
```
Some explanations for args:
- server options arguments:
  - `listening_port`: The server receives data from.
  - `ip_address_for_acks`, `port_for_acks`:  writes it to the file and sends ACKs to.
- server options arguments:
    - ` ack_port_number`:  used to receive acknowledgements.

2. run the `start.sh` file

## project structure

## Maintainer
- [Jing Peng](https://github.com/paterlisia)