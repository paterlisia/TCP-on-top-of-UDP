cd  ~/Desktop/newudpl-1.7
newudpl -i 192.168.1.210:8080 -o 192.168.1.210:8082 -B30000 -L50 -O30 -d0.6
cd ~/Desktop/CU/Courses/4119_computer_networks/project2/TCP_on_UDP
python src/app/tcpclient.py src/app/data/sendfile.txt  192.168.1.210 41192 8080 src/app/data/send_log.txt 100