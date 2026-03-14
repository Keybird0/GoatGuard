# -*- coding: UTF-8 -*-
"""
链类型自动检测

用法:
    python3 detect_chain.py 0x1234...5678
    python3 detect_chain.py So1111...
    python3 detect_chain.py 0xabcd...::module::TOKEN
"""
import sys
from typing import Tuple


def detect_chain_type(token_address: str) -> Tuple[str, str]:
    """
    自动检测链类型
    返回: (chain_type, cleaned_address)
    chain_type: evm | solana | sui | unknown
    """
    token_address = token_address.strip()

    # Sui: 包含 :: 分隔符
    if "::" in token_address:
        return "sui", token_address

    # Sui 对象地址: 0x + 64 hex = 66 chars
    if token_address.startswith("0x") and len(token_address) == 66:
        return "sui", token_address

    # EVM: 0x + 40 hex = 42 chars
    if token_address.startswith("0x") and len(token_address) == 42:
        return "evm", token_address

    # Solana: base58, 32-44 chars, 不以 0x 开头
    if not token_address.startswith("0x") and 32 <= len(token_address) <= 44:
        return "solana", token_address

    return "unknown", token_address


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 detect_chain.py <token_address>")
        sys.exit(1)
    chain, addr = detect_chain_type(sys.argv[1])
    print(f"链类型: {chain}  地址: {addr}")
