import socket
import struct
import random

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

from recursive_dns import dns_query

# Root DNS servers
ROOT_SERVERS = [
    "198.41.0.4",  # a.root-servers.net
    "199.9.14.201",  # b.root-servers.net
    "192.33.4.12",  # c.root-servers.net
]

def parse_domain_name(data, offset):
    """
    Parse a domain name from the DNS response, handling DNS name compression.

    Args:
        data (bytes): The DNS response data.
        offset (int): The current offset in the response.
    
    Returns:
        tuple: (domain_name, new_offset)
    """
    labels = []
    jumped = False
    original_offset = offset

    while True:
        length = data[offset]

        # If the first two bits are 11, it's a pointer to another part of the message (compression)
        if length >= 192:
            pointer = struct.unpack('!H', data[offset:offset + 2])[0]
            pointer &= 0x3FFF  # Remove the two most significant bits
            # logger.debug(f"Jumping to pointer location {pointer}")

            if not jumped:
                original_offset = offset + 2  # Record where we should return to
            offset = pointer  # Jump to the pointer location
            jumped = True  # Mark that we've jumped
        elif length == 0:
            offset += 1
            break
        else:
            offset += 1
            labels.append(data[offset:offset + length].decode('utf-8', errors='ignore'))
            offset += length

        # If we jumped, we stop after resolving the compressed name
        if jumped:
            break

    domain_name = '.'.join(labels)

    return domain_name, (original_offset if jumped else offset)

def iterative_dns_query(domain_name, query_type, transaction_id):
    """
    Perform iterative DNS query by querying the root DNS servers and following referrals.

    Args:
        domain_name (str): The domain name to resolve.
        query_type (int): The DNS query type.
        transaction_id (int): The transaction ID for the DNS request.
    
    Returns:
        bytes: The DNS response data from the final authoritative server.
    """
    logger.info(f"Performing iterative query for {domain_name}")
    response = None

    visited_ns = set()  # Track visited NS servers to avoid loops

    # Start by querying the root servers
    for root_server in ROOT_SERVERS:
        try:
            next_server_ip = root_server
            logger.info(f"[{domain_name}] Querying root server: {root_server}")

            while True:
                logger.info(f"[{domain_name}] Querying: {next_server_ip}")
                response = dns_query(domain_name, query_type, next_server_ip, transaction_id)
                parsed_response = parse_dns_response(response)

                # Check if we have an answer in the Answer section
                if parsed_response['answer']:
                    logger.debug(f"[{domain_name}] Found answer in response: {parsed_response['answer']}")
                    return response

                # Try to get the next server IP from the Additional section
                next_server_ip = get_next_server_ip(parsed_response)
                if next_server_ip:
                    continue # Continue to the next iteration with the new server IP

                logger.debug(f"[{domain_name}] No IP found in Additional section, attempting to resolve NS from Authority section.")

                # Extract NS records from Authority section and resolve their IPs
                ns_records = parsed_response['authority']
                for ns_record in ns_records:
                    ns_domain_name = parse_ns_record(ns_record['rdata'])
                    logger.info(f"[{domain_name}] Attempting to resolve NS record: {ns_domain_name}")
                    
                    # Resolve the NS server IP
                    ns_ip = resolve_ns_to_ip(ns_domain_name)
                    if ns_ip:
                        if ns_domain_name in visited_ns:
                            logger.error(f"[{domain_name}] Loop detected for NS record {ns_domain_name}.")
                            continue
                        next_server_ip = ns_ip
                        visited_ns.add(ns_domain_name)
                        break
                else:
                    logger.error(f"[{domain_name}] Could not find any resolvable NS records in Authority section.")
                    break
        
        except Exception as e:
            logger.exception(f"[{domain_name}] Failed querying root server {root_server}: {e}")
            continue

    logger.error(f"Failed to get response for {domain_name}")
    return response

def parse_ns_record(rdata):
    """
    Parse the NS record from rdata.

    Args:
        rdata (bytes): The raw rdata containing the NS record.
    
    Returns:
        str: The domain name of the NS record.
    """
    return parse_domain_name(rdata, 0)[0]


def resolve_ns_to_ip(ns_domain_name):
    """
    Resolve the IP address of a given NS record using a public DNS server (like 8.8.8.8).

    Args:
        ns_domain_name (str): The domain name of the NS record.
    
    Returns:
        str: The resolved IP address of the NS record, or None if resolution fails.
    """
    try:
        logger.info(f"Resolving IP for NS domain: {ns_domain_name}")
        transaction_id = random.randint(0, 65535)
        query_type = 1  # A record

        # Send query to DNS server
        # response = dns_query(ns_domain_name, query_type, ""8.8.8.8"", transaction_id)
        response = iterative_dns_query(ns_domain_name, query_type, transaction_id)
        parsed_response = parse_dns_response(response)

        # Extract IP from the answer section
        for answer in parsed_response['answer']:
            if answer['rtype'] == 1:  # A record (IPv4)
                ns_ip = socket.inet_ntoa(answer['rdata'])
                logger.debug(f"Resolved IP for {ns_domain_name}: {ns_ip}")
                return ns_ip
        return None
    except Exception as e:
        logger.exception(f"Failed to resolve IP for NS domain {ns_domain_name}: {e}")
        return None


def parse_dns_response(response):
    """
    Parse the DNS response and extract all useful information, including header, question, answer, authority, 
    and additional sections.

    Args:
        response (bytes): The raw DNS response.

    Returns:
        dict: Parsed DNS response with relevant sections.
    """
    parsed_data = {
        'header': {},
        'question': [],
        'answer': [],
        'authority': [],
        'additional': []
    }

    # Parse header (12 bytes)
    transaction_id, flags, question_count, answer_count, authority_count, additional_count = struct.unpack('!6H', response[:12])
    parsed_data['header'] = {
        'transaction_id': transaction_id,
        'flags': flags,
        'question_count': question_count,
        'answer_count': answer_count,
        'authority_count': authority_count,
        'additional_count': additional_count
    }

    offset = 12

    # Parse question section
    for _ in range(question_count):
        domain_name, offset = parse_domain_name(response, offset)
        qtype, qclass = struct.unpack('!HH', response[offset:offset + 4])
        offset += 4
        parsed_data['question'].append({
            'domain_name': domain_name,
            'qtype': qtype,
            'qclass': qclass
        })

    # Parse resource records (answer, authority, additional)
    def parse_resource_records(count, section_name):
        nonlocal offset
        records = []
        for _ in range(count):
            domain_name, offset = parse_domain_name(response, offset)
            rtype, rclass, ttl, rdata_length = struct.unpack('!HHIH', response[offset:offset + 10])
            offset += 10
            rdata = response[offset:offset + rdata_length]
            offset += rdata_length
            records.append({
                'domain_name': domain_name,
                'rtype': rtype,
                'rclass': rclass,
                'ttl': ttl,
                'rdata': rdata
            })
        parsed_data[section_name] = records

    # Parse answer, authority, and additional sections
    parse_resource_records(answer_count, 'answer')
    parse_resource_records(authority_count, 'authority')
    parse_resource_records(additional_count, 'additional')

    return parsed_data


def get_next_server_ip(parsed_data):
    """
    Extract the next DNS server IP from the Additional section of the parsed DNS response.

    Args:
        parsed_data (dict): Parsed DNS response data.

    Returns:
        str: The next DNS server IP if found, else None.
    """
    for record in parsed_data['additional']:
        if record['rtype'] == 1:  # A record (IPv4)
            next_server_ip = socket.inet_ntoa(record['rdata'])
            logger.debug(f"Next server IP (A record): {next_server_ip}")
            return next_server_ip
        elif record['rtype'] == 28:  # AAAA record (IPv6)
            next_server_ip = socket.inet_ntop(socket.AF_INET6, record['rdata'])
            logger.debug(f"Next server IP (AAAA record): {next_server_ip}")
            return next_server_ip
    return None
