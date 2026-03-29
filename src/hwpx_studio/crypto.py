#!/usr/bin/env python3
"""HWPX encryption detection and decryption.

Supports ODF-standard encryption (AES-CBC-128, Blowfish-CFB-8)
with PBKDF2-HMAC-SHA1 key derivation.

Requires: pycryptodome (Crypto) OR cryptography package.

Usage:
    python crypto.py encrypted.hwpx --password 1234 -o decrypted.hwpx
    python crypto.py encrypted.hwpx --check
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Crypto backend — try pycryptodome first, then cryptography
# ---------------------------------------------------------------------------

try:
    from Crypto.Cipher import AES as _AES, Blowfish as _Blowfish  # type: ignore
    from Crypto.Util.Padding import unpad as _unpad  # type: ignore

    def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
        cipher = _AES.new(key, _AES.MODE_CBC, iv)
        return _unpad(cipher.decrypt(data), 16)

    def _blowfish_cfb_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
        cipher = _Blowfish.new(key, _Blowfish.MODE_CFB, iv, segment_size=8)
        return cipher.decrypt(data)

    _BACKEND = "pycryptodome"

except ImportError:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore
        from cryptography.hazmat.primitives import padding as _padding  # type: ignore
        from cryptography.hazmat.backends import default_backend  # type: ignore

        def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            dec = cipher.decryptor()
            padded = dec.update(data) + dec.finalize()
            unpadder = _padding.PKCS7(128).unpadder()
            return unpadder.update(padded) + unpadder.finalize()

        def _blowfish_cfb_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
            cipher = Cipher(
                algorithms.Blowfish(key),
                modes.CFB(iv),
                backend=default_backend(),
            )
            dec = cipher.decryptor()
            return dec.update(data) + dec.finalize()

        _BACKEND = "cryptography"

    except ImportError as exc:
        raise ImportError(
            "crypto.py requires pycryptodome or cryptography. "
            "Install one: pip install pycryptodome  OR  pip install cryptography"
        ) from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EncryptedDocumentError(Exception):
    """Raised when a document is encrypted and no password was provided."""


class WrongPasswordError(Exception):
    """Raised when the provided password is incorrect."""


class UnsupportedEncryptionError(Exception):
    """Raised when the encryption algorithm is not supported."""


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

# ODF manifest namespace
_MANIFEST_NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
_MANIFEST_PATH = "META-INF/manifest.xml"

# Supported algorithms
_SUPPORTED_ALGOS = {
    "http://www.w3.org/2001/04/xmlenc#aes128-cbc": "AES-CBC-128",
    "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0#blowfish-cfb-8": "Blowfish-CFB-8",
    # Hancom variant URIs
    "http://www.hancom.com/sec/aes128-cbc": "AES-CBC-128",
    "http://www.hancom.com/sec/blowfish-cfb-8": "Blowfish-CFB-8",
}


@dataclass
class _EncryptionEntry:
    entry_path: str
    algorithm_uri: str
    algorithm_name: str
    key_size: int        # bytes
    iteration_count: int
    salt: bytes
    init_vector: bytes
    checksum: bytes
    checksum_type: str


def _parse_manifest(manifest_xml: bytes) -> list[_EncryptionEntry]:
    """Parse META-INF/manifest.xml and return entries that have encryption-data."""
    root = ET.fromstring(manifest_xml)
    ns = _MANIFEST_NS
    entries: list[_EncryptionEntry] = []

    for file_entry in root.findall(f"{{{ns}}}file-entry"):
        enc_data = file_entry.find(f"{{{ns}}}encryption-data")
        if enc_data is None:
            continue

        algo_el = enc_data.find(f"{{{ns}}}algorithm")
        key_deriv_el = enc_data.find(f"{{{ns}}}key-derivation")
        checksum_el = enc_data.find(f"{{{ns}}}start-key-generation")
        # Fallback for ODF 1.2 variant
        if checksum_el is None:
            checksum_el = enc_data

        entry_path = file_entry.get(f"{{{ns}}}full-path", "")
        algorithm_uri = algo_el.get(f"{{{ns}}}algorithm-name", "") if algo_el is not None else ""
        init_vector_b64 = algo_el.get(f"{{{ns}}}initialisation-vector", "") if algo_el is not None else ""

        key_size = int(key_deriv_el.get(f"{{{ns}}}key-size", "16")) if key_deriv_el is not None else 16
        iteration_count = int(key_deriv_el.get(f"{{{ns}}}iteration-count", "1024")) if key_deriv_el is not None else 1024
        salt_b64 = key_deriv_el.get(f"{{{ns}}}salt", "") if key_deriv_el is not None else ""

        checksum_type = enc_data.get(f"{{{ns}}}checksum-type", "")
        checksum_b64 = enc_data.get(f"{{{ns}}}checksum", "")

        import base64
        try:
            iv = base64.b64decode(init_vector_b64) if init_vector_b64 else b""
            salt = base64.b64decode(salt_b64) if salt_b64 else b""
            checksum = base64.b64decode(checksum_b64) if checksum_b64 else b""
        except Exception:
            iv = salt = checksum = b""

        algorithm_name = _SUPPORTED_ALGOS.get(algorithm_uri, "")
        if not algorithm_name and algorithm_uri:
            # Try case-insensitive / partial match
            for uri, name in _SUPPORTED_ALGOS.items():
                if algorithm_uri.lower().endswith(uri.lower().rsplit("/", 1)[-1]):
                    algorithm_name = name
                    break

        entries.append(
            _EncryptionEntry(
                entry_path=entry_path,
                algorithm_uri=algorithm_uri,
                algorithm_name=algorithm_name,
                key_size=key_size,
                iteration_count=iteration_count,
                salt=salt,
                init_vector=iv,
                checksum=checksum,
                checksum_type=checksum_type,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _derive_key(password: str, salt: bytes, iteration_count: int, key_size: int) -> bytes:
    """PBKDF2-HMAC-SHA1 key derivation (ODF standard)."""
    password_bytes = password.encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha1",
        password_bytes,
        salt,
        iteration_count,
        dklen=key_size,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_encryption(hwpx_path: str | Path) -> list[_EncryptionEntry]:
    """Return a list of encrypted entries found in the HWPX file.

    Returns an empty list if the document is not encrypted.
    Raises zipfile.BadZipFile if the path is not a valid ZIP/HWPX.
    """
    hwpx_path = Path(hwpx_path)
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        if _MANIFEST_PATH not in zf.namelist():
            return []
        manifest_xml = zf.read(_MANIFEST_PATH)

    return _parse_manifest(manifest_xml)


def is_encrypted(hwpx_path: str | Path) -> bool:
    """Return True if the HWPX file contains any encrypted entries."""
    try:
        return len(detect_encryption(hwpx_path)) > 0
    except (zipfile.BadZipFile, OSError):
        return False


def decrypt_file(
    hwpx_path: str | Path,
    password: str,
    output_path: str | Path,
) -> None:
    """Decrypt an encrypted HWPX file and write the result to output_path.

    Raises:
        EncryptedDocumentError: if the file is not encrypted (nothing to decrypt).
        WrongPasswordError: if the password verification fails.
        UnsupportedEncryptionError: if the algorithm is not AES-CBC-128 or Blowfish-CFB-8.
        zipfile.BadZipFile: if the input is not a valid ZIP.
    """
    hwpx_path = Path(hwpx_path)
    output_path = Path(output_path)

    entries = detect_encryption(hwpx_path)
    if not entries:
        raise EncryptedDocumentError(f"{hwpx_path} does not appear to be encrypted.")

    # Check for unsupported algorithms
    for entry in entries:
        if entry.algorithm_uri and not entry.algorithm_name:
            raise UnsupportedEncryptionError(
                f"Unsupported encryption algorithm: {entry.algorithm_uri}"
            )

    # Build a set of paths that need decryption
    enc_map: dict[str, _EncryptionEntry] = {e.entry_path: e for e in entries}

    import base64

    # We'll verify password using the first entry with a checksum
    verified = False
    decrypt_errors: list[str] = []

    with zipfile.ZipFile(hwpx_path, "r") as zf_in:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
            # mimetype must be first entry, stored uncompressed
            names = zf_in.namelist()
            ordered = []
            if "mimetype" in names:
                ordered.append("mimetype")
            ordered += [n for n in names if n != "mimetype"]

            for name in ordered:
                raw = zf_in.read(name)

                if name not in enc_map:
                    compress = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
                    zf_out.writestr(
                        zipfile.ZipInfo(name),
                        raw,
                        compress_type=compress,
                    )
                    continue

                entry = enc_map[name]

                # Derive key
                key = _derive_key(password, entry.salt, entry.iteration_count, entry.key_size)

                # Decrypt
                try:
                    if entry.algorithm_name == "AES-CBC-128":
                        decrypted = _aes_cbc_decrypt(key, entry.init_vector, raw)
                    elif entry.algorithm_name == "Blowfish-CFB-8":
                        decrypted = _blowfish_cfb_decrypt(key, entry.init_vector, raw)
                    else:
                        raise UnsupportedEncryptionError(
                            f"Unsupported algorithm: {entry.algorithm_name}"
                        )
                except Exception as exc:
                    if "padding" in str(exc).lower() or "unpad" in str(exc).lower():
                        raise WrongPasswordError(
                            f"Wrong password (padding error on {name})."
                        ) from exc
                    raise

                # Verify checksum if available (SHA1 of decrypted content)
                if entry.checksum and not verified:
                    sha1 = hashlib.sha1(decrypted).digest()
                    # ODF checksum is SHA1 of first 1024 bytes
                    sha1_1k = hashlib.sha1(decrypted[:1024]).digest()
                    if sha1 != entry.checksum and sha1_1k != entry.checksum:
                        raise WrongPasswordError(
                            "Wrong password (checksum mismatch)."
                        )
                    verified = True

                zf_out.writestr(name, decrypted)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect and decrypt encrypted HWPX files"
    )
    parser.add_argument("input", help="Path to (possibly encrypted) .hwpx file")
    parser.add_argument(
        "--password", "-p",
        help="Decryption password",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for decrypted .hwpx file",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the file is encrypted (no decryption)",
    )
    args = parser.parse_args()

    if not Path(args.input).is_file():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    entries = detect_encryption(args.input)

    if args.check:
        if entries:
            algos = {e.algorithm_name or e.algorithm_uri for e in entries}
            print(f"Encrypted: YES  ({', '.join(algos)}, {len(entries)} entries)")
        else:
            print("Encrypted: NO")
        return

    if not entries:
        print(f"{args.input} is not encrypted — nothing to do.")
        return

    if not args.password:
        print("Error: --password required for decryption.", file=sys.stderr)
        sys.exit(1)

    if not args.output:
        print("Error: --output required for decryption.", file=sys.stderr)
        sys.exit(1)

    try:
        decrypt_file(args.input, args.password, args.output)
        print(f"Decrypted: {args.output}  (backend: {_BACKEND})")
    except WrongPasswordError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except UnsupportedEncryptionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
