# ECE4016 - Assignment 1

## Student ID: 122090513
## Student Name: Wang Chaoren


## How to run the code

1. Install Python 3.9
2. Run the following commands in the terminal
```bash
python3 -m venv venv # optional
source venv/bin/activate # optional
pip install loguru # optional, for better logging

python main.py # Run the recursive version, query the public DNS server
python main.py --iterative # Run the iterative version
```


## Check the result
```bash
dig www.example.com @127.0.0.1 -p 1234

# ; <<>> DiG 9.10.6 <<>> www.example.com @127.0.0.1 -p 1234
# ;; global options: +cmd
# ;; Got answer:
# ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 10390
# ;; flags: qr aa rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0
# ;; WARNING: recursion requested but not available

# ;; QUESTION SECTION:
# ;www.example.com.               IN      A

# ;; ANSWER SECTION:
# www.example.com.        3600    IN      A       93.184.215.14

# ;; Query time: 1098 msec
# ;; SERVER: 127.0.0.1#1234(127.0.0.1)
# ;; WHEN: Fri Oct 11 16:20:22 CST 2024
# ;; MSG SIZE  rcvd: 49

dig www.baidu.com @127.0.0.1 -p 1234

# ; <<>> DiG 9.10.6 <<>> www.baidu.com @127.0.0.1 -p 1234
# ;; global options: +cmd
# ;; Got answer:
# ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 30012
# ;; flags: qr aa rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0
# ;; WARNING: recursion requested but not available

# ;; QUESTION SECTION:
# ;www.baidu.com.                 IN      A

# ;; ANSWER SECTION:
# www.baidu.com.          1200    IN      CNAME   www.a.shifen.com.

# ;; Query time: 405 msec
# ;; SERVER: 127.0.0.1#1234(127.0.0.1)
# ;; WHEN: Fri Oct 11 16:20:55 CST 2024
# ;; MSG SIZE  rcvd: 61
```