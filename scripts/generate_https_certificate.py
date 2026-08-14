from __future__ import annotations

import argparse
import ipaddress
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _normalize_ips(ip_values: str | list[str]) -> list[str]:
    values = [ip_values] if isinstance(ip_values, str) else ip_values
    normalized: list[str] = []
    for value in values:
        ip_value = str(ipaddress.ip_address(value.strip()))
        if ip_value not in normalized:
            normalized.append(ip_value)
    if not normalized:
        raise ValueError("Informe ao menos um endereço IP para o certificado.")
    return normalized


def _load_or_create_ca(output: Path, now: datetime) -> tuple[object, x509.Certificate]:
    ca_certificate_path = output / "doutrinador-ca.crt"
    ca_key_path = output / "doutrinador-ca.key"
    if ca_certificate_path.exists() and ca_key_path.exists():
        ca_certificate = x509.load_pem_x509_certificate(ca_certificate_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        return ca_key, ca_certificate

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Doutrinador Local CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Projeto Doutrinador"),
    ])
    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=False, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_certificate_path.write_bytes(ca_certificate.public_bytes(serialization.Encoding.PEM))
    ca_key_path.write_bytes(ca_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    try:
        os.chmod(ca_key_path, 0o600)
    except OSError:
        pass
    return ca_key, ca_certificate


def generate(ip_values: str | list[str], output: Path) -> dict[str, object]:
    ips = _normalize_ips(ip_values)
    output.mkdir(parents=True, exist_ok=True)
    info_path = output / "certificate-info.json"
    expected = {
        "ip": ips[0],
        "ips": ips,
        "ca_certificate": "doutrinador-ca.crt",
        "ca_key": "doutrinador-ca.key",
        "server_certificate": "doutrinador-server.crt",
        "server_key": "doutrinador-server.key",
    }
    required = [
        output / str(expected[key])
        for key in ("ca_certificate", "ca_key", "server_certificate", "server_key")
    ]
    if info_path.exists() and all(path.exists() for path in required):
        try:
            stored = json.loads(info_path.read_text(encoding="utf-8"))
            stored_ips = stored.get("ips") or [stored.get("ip")]
            if stored_ips == ips:
                return expected
        except (OSError, json.JSONDecodeError):
            pass

    now = datetime.now(UTC)
    ca_key, ca_certificate = _load_or_create_ca(output, now)

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    server_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ips[0]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Projeto Doutrinador"),
    ])
    server_certificate = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_certificate.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=397))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(value)) for value in ips]
                + [x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    (output / str(expected["server_certificate"])).write_bytes(
        server_certificate.public_bytes(serialization.Encoding.PEM)
    )
    key_path = output / str(expected["server_key"])
    key_path.write_bytes(server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    info_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera certificado HTTPS local do Doutrinador.")
    parser.add_argument(
        "--ip",
        action="append",
        dest="ips",
        help="Endereço IP aceito pelo certificado; repita a opção para LAN e VPN.",
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = generate(arguments.ips or ["192.168.10.105"], arguments.output.resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
