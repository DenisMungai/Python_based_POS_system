"""Pure-Python Code 128-B and EAN-13 barcode encoders."""

from backend.core.errors import ValidationError

_CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112",
    "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412",
    "211214", "211232", "2331112",
)


def _runs_to_bits(pattern: str) -> str:
    bit = "1"
    output: list[str] = []
    for run in pattern:
        output.append(bit * int(run))
        bit = "0" if bit == "1" else "1"
    return "".join(output)


def encode_code128(value: str) -> str:
    """Return Code 128-B module bits, including the stop pattern."""
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValidationError("Code 128-B accepts printable ASCII characters.")
    codes = [104, *(ord(char) - 32 for char in value)]
    checksum = (codes[0] + sum(index * code for index, code in enumerate(codes[1:], 1))) % 103
    return "".join(_runs_to_bits(_CODE128_PATTERNS[code]) for code in (*codes, checksum, 106))


def encode_ean13(value: str) -> str:
    """Return the 95 EAN-13 symbol modules for a 12- or 13-digit value."""
    if not value.isdigit() or len(value) not in (12, 13):
        raise ValidationError("EAN-13 requires 12 or 13 digits.")
    digits = [int(char) for char in value]
    checksum = (10 - sum(digit * (1 if index % 2 == 0 else 3) for index, digit in enumerate(digits[:12])) % 10) % 10
    if len(digits) == 13 and digits[12] != checksum:
        raise ValidationError("EAN-13 check digit is invalid.")
    digits = digits[:12] + [checksum]
    first_patterns = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
                      "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")
    left = {
        "L": ("0001101", "0011001", "0010011", "0111101", "0100011",
              "0110001", "0101111", "0111011", "0110111", "0001011"),
        "G": ("0100111", "0110011", "0011011", "0100001", "0011101",
              "0111001", "0000101", "0010001", "0001001", "0010111"),
    }
    right = ("1110010", "1100110", "1101100", "1000010", "1011100",
             "1001110", "1010000", "1000100", "1001000", "1110100")
    parity = first_patterns[digits[0]]
    return (
        "101"
        + "".join(left[parity[index]][digits[index + 1]] for index in range(6))
        + "01010"
        + "".join(right[digits[index]] for index in range(7, 13))
        + "101"
    )
