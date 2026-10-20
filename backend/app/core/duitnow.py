"""DuitNow QR codes follow the EMVCo merchant QR format: tag-length-value fields ending in a
CRC-16/CCITT checksum (tag 63). Checking it catches a code that was copied or typed wrongly
before customers scan it."""


def crc16(text: str) -> str:
    """CRC-16/CCITT-FALSE as four upper-case hex digits, as the QR format uses."""
    crc = 0xFFFF
    for byte in text.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def is_valid_qr(payload: str) -> bool:
    """A complete merchant QR: starts with the format indicator field (tag 00; banks differ
    in its value), ends with a matching CRC."""
    return (
        payload.startswith("0002")
        and len(payload) > 8
        and payload[-8:-4] == "6304"
        and crc16(payload[:-4]) == payload[-4:].upper()
    )
