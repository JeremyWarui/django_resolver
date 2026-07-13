"""apps/accounts/mail_backend.EmailBackend — IPv4-only SMTP connection.

Render has no outbound IPv6 route to Gmail; smtp.gmail.com resolves to both
an A and AAAA record, and the stock Django SMTP backend fails outright with
`OSError: [Errno 101] Network is unreachable` when it tries the AAAA address.
These tests confirm the connection helper only ever asks for/attempts AF_INET
addresses, without touching the real network.
"""

import socket

import pytest

from apps.accounts.mail_backend import EmailBackend, IPv4SMTP, _create_ipv4_connection


class _FakeSocket:
    def __init__(self, family, socktype, proto):
        self.family = family
        self.connected = None

    def settimeout(self, timeout):
        pass

    def bind(self, address):
        pass

    def connect(self, sockaddr):
        self.connected = sockaddr

    def close(self):
        pass


def test_create_ipv4_connection_only_requests_af_inet(monkeypatch):
    requested_families = []

    def fake_getaddrinfo(host, port, family, socktype):
        requested_families.append(family)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "socket", _FakeSocket)

    sock = _create_ipv4_connection(("smtp.gmail.com", 587), 10, None)

    assert requested_families == [socket.AF_INET]
    assert sock.connected == ("smtp.gmail.com", 587)


def test_create_ipv4_connection_raises_if_all_attempts_fail(monkeypatch):
    def fake_getaddrinfo(host, port, family, socktype):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    class _UnreachableSocket(_FakeSocket):
        def connect(self, sockaddr):
            raise OSError("Network is unreachable")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "socket", _UnreachableSocket)

    with pytest.raises(OSError, match="Network is unreachable"):
        _create_ipv4_connection(("smtp.gmail.com", 587), 10, None)


def test_email_backend_connection_class_is_ipv4_smtp():
    backend = EmailBackend()
    assert backend.connection_class is IPv4SMTP


def test_email_backend_rejects_ssl():
    backend = EmailBackend(use_ssl=True, use_tls=False)
    with pytest.raises(NotImplementedError):
        backend.connection_class
