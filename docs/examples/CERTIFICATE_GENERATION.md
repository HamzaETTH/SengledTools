# Certificate Generation with OpenSSL

This guide provides the OpenSSL commands to generate the necessary TLS certificates
## Windows

```bash
# Create a local CA
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" genrsa -out ca.key 2048
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" req -x509 -new -key ca.key -days 3650 -out ca.crt -subj "/CN=Local-CA"

# Create server key + CSR (use any descriptive CN, e.g., broker.local)
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" genrsa -out server.key 2048
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" req -new -key server.key -out server.csr -subj "/CN=broker.local"

# Sign server cert
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3650 -sha256
```

## Linux

```bash
# Create a local CA
openssl genrsa -out ca.key 2048
openssl req -x509 -new -key ca.key -days 3650 -out ca.crt -subj "/CN=Local-CA"

# Create server key + CSR (use any descriptive CN, e.g., broker.local)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=broker.local"

# Sign server cert
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3650 -sha256
```
