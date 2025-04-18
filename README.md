# Pump Fun Token Launcher

A command-line tool for creating tokens on Solana using the Pump Fun protocol. This tool directly interacts with the Pump Fun smart contract and IDL, providing a fast and efficient way to launch tokens with optional initial liquidity.

## Overview

Pump Fun is a decentralized protocol on Solana that enables token creation with built-in bonding curves. This launcher bypasses the web interface and directly interacts with the protocol's smart contract (program ID: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`).

## Key Features

- Direct interaction with Pump Fun smart contract and IDL
- Token creation with Metaplex-compliant metadata
- Optional initial liquidity provision (dev buy)
- IPFS metadata storage via Pinata
- Interactive CLI for easy token configuration
- Full control over token parameters

## Prerequisites

- Python 3.7+
- Solana CLI tools
- SOL for transaction fees
- (Optional) Pinata API keys for IPFS storage

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/Timaxsss/Pumpfun-Launcher.git
cd Pumpfun-Launcher
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Run the launcher:
```bash
python create.py
```

## Technical Implementation

The launcher works by:
1. Calculating required PDAs (Program Derived Addresses)
2. Constructing transactions using Pump Fun's instruction format
3. Creating token metadata following Metaplex standards
4. Deploying to Solana mainnet
5. Optionally providing initial liquidity

## Security Notes

- Never commit your `.env` file
- Use a dedicated wallet for token creation
- Verify all transaction details before confirming
- Keep your private keys secure

## License

MIT License - See LICENSE file for details 