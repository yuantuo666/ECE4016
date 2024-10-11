import socket
import struct

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

def build_dns_query(domain_name, query_type, transaction_id):
    """
    Build the DNS query packet based on the domain name, query type, and transaction ID.

    Args:
        domain_name (str): The domain name to resolve.
        query_type (int): The type of DNS query (e.g., A, AAAA).
        transaction_id (int): The transaction ID for the DNS request.
    
    Returns:
        bytes: The DNS query packet to send to the DNS server.
    """
    flags = 0x0100  # Standard query with recursion
    header = struct.pack('!HHHHHH', transaction_id, flags, 1, 0, 0, 0)

    # Encode the domain name
    question = b''.join(struct.pack('B', len(label)) + label.encode('utf-8') for label in domain_name.split('.'))
    question += b'\x00'  # End of domain name
    question += struct.pack('!HH', query_type, 1)  # Query type and class (IN = 1)

    request = header + question
    
    logger.debug(f"Built DNS query for {domain_name}: {request = }")

    return request


def dns_query(domain_name, query_type, dns_server, transaction_id, timeout=2):
    """
    Perform a DNS query to a specified DNS server with a timeout mechanism.

    Args:
        domain_name (str): The domain name to resolve.
        query_type (int): The DNS query type.
        dns_server (str): The DNS server IP to query.
        transaction_id (int): The transaction ID for the DNS request.
        timeout (int): The timeout in seconds for the socket operation (default 2 seconds).
    
    Returns:
        bytes: The raw response data from the DNS server.
    
    Raises:
        socket.timeout: If the request times out.
        Exception: For other socket-related errors.
    """
    query_packet = build_dns_query(domain_name, query_type, transaction_id)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)  # Set timeout for the socket
        try:
            logger.debug(f"Sending query to DNS server {dns_server} with timeout {timeout}s")
            sock.sendto(query_packet, (dns_server, 53))
            response, _ = sock.recvfrom(512)
            logger.debug(f"Received response from {dns_server}: {response = }.")
            return response
        except socket.timeout:
            logger.error(f"Query to DNS server {dns_server} timed out after {timeout} seconds")
            raise
        except Exception as e:
            logger.exception(f"Error during DNS query to {dns_server}: {e}")
            raise



def is_answer(response):
    """
    Check if the DNS response contains an answer.

    Args:
        response (bytes): The DNS response.

    Returns:
        bool: True if the response contains an answer, False otherwise.
    """
    flags = struct.unpack('!H', response[2:4])[0]
    answer_count = struct.unpack('!H', response[6:8])[0]
    return (flags & 0x8000 != 0) and answer_count > 0
