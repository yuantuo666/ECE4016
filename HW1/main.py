import socket
import struct

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    logger.info("Using logging module instead of loguru. Recommend installing loguru for a better experience: `pip install loguru`")

from iterative_dns import iterative_dns_query
from recursive_dns import dns_query


def resolve_dns_query(domain_name, query_type, transaction_id, iterative):
    """
    Resolve DNS query either iteratively or by forwarding to a public DNS server.

    Args:
        domain_name (str): The domain name to resolve.
        query_type (int): The DNS query type.
        transaction_id (int): The transaction ID for the DNS request.
        iterative (bool): Whether to use iterative DNS resolution.
    
    Returns:
        bytes: The DNS response data.
    """
    if iterative:
        return iterative_dns_query(domain_name, query_type, transaction_id)

    # Use a public DNS server (8.8.8.8)
    logger.info(f"Performing iterative query for {domain_name} using public DNS")
    return dns_query(domain_name, query_type, "8.8.8.8", transaction_id)


def modify_transaction_id(response, new_transaction_id):
    """
    Modify the transaction ID of a DNS response to match the new query's transaction ID.

    Args:
        response (bytes): The original DNS response packet.
        new_transaction_id (int): The new transaction ID from the current query.
    
    Returns:
        bytes: The modified DNS response packet with the new transaction ID.
    """
    return struct.pack('!H', new_transaction_id) + response[2:]


def start_dns_server(server_ip, port, iterative):
    """
    Start the local DNS server to listen for incoming DNS queries and respond accordingly.

    Args:
        server_ip (str): The IP address for the local DNS server.
        port (int): The port for the local DNS server.
        iterative (bool): Whether to perform iterative DNS resolution.
    """
    cache = {}
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, port))
    logger.info(f"Local DNS server started on {server_ip}:{port}")

    while True:
        data, addr = server_socket.recvfrom(512)
        logger.info(f"Received DNS query from {addr}")

        # Parse DNS query
        transaction_id, domain_name, query_type = parse_dns_query(data)

        # Check cache
        if domain_name in cache:
            cached_response = cache[domain_name]
            response = modify_transaction_id(cached_response, transaction_id) # ;; Warning: ID mismatch: expected ID 50391, got 42449
            logger.info(f"Sent cached response for {domain_name}")
        else:
            # Resolve query (iterative or iterative)
            response = resolve_dns_query(domain_name, query_type, transaction_id, iterative)
            cache[domain_name] = response
            logger.info(f"Sent response for {domain_name} and cached it.")

        server_socket.sendto(response, addr)


def parse_dns_query(data):
    """
    Parse the incoming DNS query and extract the transaction ID, domain name, and query type.

    Args:
        data (bytes): The raw DNS query data.
    
    Returns:
        tuple: (transaction_id, domain_name, query_type)
    """
    transaction_id = struct.unpack('!H', data[:2])[0]
    domain_name = ''
    offset = 12
    
    while True:
        length = data[offset]
        if length == 0:
            break
        domain_name += data[offset + 1:offset + 1 + length].decode('utf-8') + '.'
        offset += length + 1
    
    query_type = struct.unpack('!HH', data[offset + 1:offset + 5])[0]
    return transaction_id, domain_name.strip('.'), query_type


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Local DNS Server")
    parser.add_argument("--server_ip", type=str, default="127.0.0.1", help="The IP address for the local DNS server")
    parser.add_argument("--port", type=int, default=1234, help="The port for the local DNS server")
    parser.add_argument("--iterative", action="store_true", help="Use iterative DNS resolution")
    
    args = parser.parse_args()

    # Start the DNS server with parsed arguments
    start_dns_server(args.server_ip, args.port, args.iterative)

"""
Usage examples:
    python dns_server.py --server_ip 127.0.0.1 --port 1234 --iterative
    python dns_server.py --server_ip 192.168.1.10 --port 5353
"""
