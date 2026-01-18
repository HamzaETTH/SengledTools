"""
Embedded MQTT broker with TLS support for local Sengled bulb communication.
Generates CA and server certificates, runs an amqtt broker on port 8883,
and accepts anonymous connections from bulbs without client certificates.
"""

import asyncio
import ssl
import threading
import logging
from ipaddress import ip_address
from sengled.log import info, success, debug, waiting, warn
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
from typing import Optional

from amqtt.broker import Broker
from amqtt.errors import BrokerError

from sengled.utils import get_local_ip
from sengled.constants import DEFAULT_BROKER_PORT as BROKER_TLS_PORT


def generate_certificates(cert_dir: Path, force_regenerate: bool = False):
    """Generate CA and server certificates if they don't exist or if forced."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    ca_key_path = cert_dir / "ca.key"
    ca_cert_path = cert_dir / "ca.crt"
    server_key_path = cert_dir / "server.key"
    server_cert_path = cert_dir / "server.crt"
    
    # Check if all files exist
    if not force_regenerate and all(p.exists() for p in [ca_key_path, ca_cert_path, server_key_path, server_cert_path]):
        debug("Certificates already exist, skipping generation")
        return ca_cert_path, server_cert_path, server_key_path
    
    waiting("Generating TLS certificates (this may take a few seconds)...")
    
    # Generate CA private key
    ca_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate CA certificate
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Local-CA"),
    ])
    
    ca_cert = x509.CertificateBuilder().subject_name(
        ca_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        ca_private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(ca_private_key.public_key()), critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key()), critical=False
    ).sign(ca_private_key, hashes.SHA256())
    
    # Generate server private key
    server_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate server certificate
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "broker.local"),
    ])
    
    server_cert = x509.CertificateBuilder().subject_name(
        server_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        server_private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("broker.local"),
            x509.IPAddress(ip_address("127.0.0.1")),
            x509.IPAddress(ip_address("0.0.0.0")),
            x509.IPAddress(ip_address(get_local_ip())),
        ]), critical=False
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            content_commitment=False,
            data_encipherment=False,
            encipher_only=False,
            decipher_only=False
        ), critical=True
    ).add_extension(
        x509.ExtendedKeyUsage([
            x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
        ]), critical=False
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(server_private_key.public_key()), critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key()), critical=False
    ).sign(ca_private_key, hashes.SHA256())
    
    # Write files
    with open(ca_key_path, "wb") as f:
        f.write(ca_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(ca_cert_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    
    with open(server_key_path, "wb") as f:
        f.write(server_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(server_cert_path, "wb") as f:
        f.write(server_cert.public_bytes(serialization.Encoding.PEM))
    
    success(f"Generated certificates in {cert_dir}")
    return ca_cert_path, server_cert_path, server_key_path


# Monkey-patch to disable client-cert requests
# The amqtt library by default requires client certificates, but Sengled bulbs
# don't provide them. This patch creates a more permissive SSL context.
def _no_client_auth_create_ssl_context(self, listener):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(listener["certfile"], listener["keyfile"])
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384")
    except Exception:
        pass
    try:
        ctx.set_ecdh_curve("prime256v1")
    except Exception:
        pass
    return ctx

Broker._create_ssl_context = _no_client_auth_create_ssl_context


class EmbeddedBroker:
    def __init__(self, cert_dir: Path, force_regenerate: bool = False, verbose: bool = False):
        self.cert_dir = cert_dir
        self.force_regenerate = force_regenerate
        self.verbose = verbose
        self.config = None
        self._broker = None
        self.loop = None
        self.startup_exception: Optional[Exception] = None
        self.started = threading.Event()
        self.is_running = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

        self._prepare_certs()
        self._build_config()
        self._configure_logging()

    def _prepare_certs(self):
        """Generate or validate certificate files for the broker."""
        self.ca_file, self.cert_file, self.key_file = generate_certificates(
            self.cert_dir, force_regenerate=self.force_regenerate
        )

    def _build_config(self):
        listener_config = {
            "type": "tcp",
            "bind": f"0.0.0.0:{BROKER_TLS_PORT}",
            "ssl": True,
            "certfile": str(self.cert_file),
            "keyfile": str(self.key_file),
        }
            
        self.config = {
            "listeners": {
                "default": listener_config,
            },
            "timeout_disconnect_delay": 0,
            "plugins": {
                "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                    "allow_anonymous": True
                }
            },
        }

    def _configure_logging(self):
        """Configure amqtt logging based on verbose mode."""
        log_level = logging.DEBUG if self.verbose else logging.CRITICAL
        amqtt_logger = logging.getLogger("amqtt")
        
        # Prevent amqtt from printing its own tracebacks on connection errors
        amqtt_logger.setLevel(log_level)
        amqtt_logger.propagate = False

        # Always use NullHandler to completely silence amqtt
        if not amqtt_logger.handlers:
            amqtt_logger.addHandler(logging.NullHandler())

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def start_broker():
            self._broker = Broker(self.config, loop=self.loop)
            await self._broker.start()

        try:
            self.loop.run_until_complete(start_broker())
            self.is_running.set()
            self.started.set()
            self.loop.run_forever()
        except Exception as e:
            is_port_busy = False
            if isinstance(e, BrokerError) and e.__cause__:
                if isinstance(e.__cause__, PermissionError) and e.__cause__.errno == 13:
                    is_port_busy = True
            
            if is_port_busy:
                clean_error = BrokerError("Port 8883 is in use or requires administrator privileges.")
                clean_error.__cause__ = None
                self.startup_exception = clean_error
            else:
                self.startup_exception = e
            
            self.started.set()
        finally:
            if self.loop.is_running():
                self.loop.stop()
            self.is_running.clear()

    def start(self):
        waiting("Starting MQTT broker...")
        self.thread.start()
        started = self.started.wait(timeout=10)
        
        if not started:
            raise RuntimeError("MQTT broker thread failed to report status within 10 seconds.")
        
        if self.startup_exception:
            raise self.startup_exception

    def stop(self):
        if not self.thread.is_alive() or not self.loop:
            return

        if self.loop.is_running():
            async def _shutdown():
                if self._broker:
                    await self._broker.shutdown()
                self.loop.stop()

            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)

        self.thread.join(timeout=5)
        if self.thread.is_alive():
            warn("MQTT broker thread did not stop gracefully.")
        else:
            success("MQTT broker stopped")


# Example usage:
# 
# # Auto-generate certificates in 'certs' directory
# broker = EmbeddedBroker(cert_dir=Path("certs"))
# 
# # Or use existing certificates
# broker = EmbeddedBroker(
#     key_file=Path("certs/server.key"),
#     cert_file=Path("certs/server.crt"),
#     ca_file=Path("certs/ca.crt")
# )


