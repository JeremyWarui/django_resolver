"""SMTP email backend that connects over IPv4 only.

smtp.gmail.com resolves to both an A (IPv4) and AAAA (IPv6) record. Render's
outbound network has no working IPv6 route to it -- attempting the AAAA
address fails immediately with `OSError: [Errno 101] Network is unreachable`
(confirmed in production logs), even though the IPv4 address is reachable.
smtplib/socket.create_connection tries every getaddrinfo() result and only
raises once all of them fail, so a dead IPv6 route in the list is enough to
break delivery outright. Restricting resolution to AF_INET sidesteps it.

Only the STARTTLS (EMAIL_USE_TLS) path is implemented -- this project never
sets EMAIL_USE_SSL.
"""

import smtplib
import socket

from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


def _create_ipv4_connection(address, timeout, source_address):
    host, port = address
    err = None
    for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    ):
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            err = exc
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    raise OSError(f"No IPv4 address found for {host!r}")


class IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        if timeout is not None and not timeout:
            raise ValueError("Non-blocking socket (timeout=0) is not supported")
        return _create_ipv4_connection((host, port), timeout, self.source_address)


class EmailBackend(SMTPEmailBackend):
    """Drop-in replacement for django.core.mail.backends.smtp.EmailBackend
    that forces the SMTP connection over IPv4."""

    @property
    def connection_class(self):
        if self.use_ssl:
            raise NotImplementedError(
                "EMAIL_USE_SSL is not supported by apps.accounts.mail_backend "
                "-- this project only uses STARTTLS."
            )
        return IPv4SMTP
