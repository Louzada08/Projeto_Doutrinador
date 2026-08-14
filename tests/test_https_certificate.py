import ipaddress
import tempfile
import unittest
from pathlib import Path

from cryptography import x509

from scripts.generate_https_certificate import generate


class HttpsCertificateTests(unittest.TestCase):
    def test_certificado_aceita_enderecos_da_lan_e_da_vpn(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = generate(["192.168.10.105", "10.66.66.1"], output)

            certificate = x509.load_pem_x509_certificate(
                (output / "doutrinador-server.crt").read_bytes()
            )
            alternative_names = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value

            self.assertEqual(result["ips"], ["192.168.10.105", "10.66.66.1"])
            self.assertEqual(
                set(alternative_names.get_values_for_type(x509.IPAddress)),
                {
                    ipaddress.ip_address("192.168.10.105"),
                    ipaddress.ip_address("10.66.66.1"),
                    ipaddress.ip_address("127.0.0.1"),
                },
            )
            self.assertEqual(
                alternative_names.get_values_for_type(x509.DNSName), ["localhost"]
            )
            self.assertTrue((output / "doutrinador-ca.key").exists())

    def test_alterar_ips_reaproveita_a_autoridade_certificadora(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate("192.168.10.105", output)
            original_ca = (output / "doutrinador-ca.crt").read_bytes()

            generate(["192.168.10.105", "10.66.66.1"], output)

            self.assertEqual((output / "doutrinador-ca.crt").read_bytes(), original_ca)
            certificate = x509.load_pem_x509_certificate(
                (output / "doutrinador-server.crt").read_bytes()
            )
            names = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value
            self.assertIn(
                ipaddress.ip_address("10.66.66.1"),
                names.get_values_for_type(x509.IPAddress),
            )


if __name__ == "__main__":
    unittest.main()
