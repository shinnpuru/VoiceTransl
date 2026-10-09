"""Explicit proxy routing shared by model tests and translation requests."""
import ipaddress
from urllib.parse import urlsplit
import requests


def is_loopback_endpoint(endpoint):
    host = (urlsplit(str(endpoint)).hostname or '').rstrip('.').lower()
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or bool(
            getattr(address, 'ipv4_mapped', None) and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def model_request(method, url, proxy=None, **kwargs):
    with requests.Session() as session:
        session.trust_env = False
        if proxy and not is_loopback_endpoint(url):
            session.proxies.update({'http': proxy, 'https': proxy})
        return session.request(method, url, **kwargs)
