# Pump Fun Token Creator

A Python script that enables direct token creation on Solana through the terminal, bypassing the potentially slow Pump Fun web interface. It uses the Pump Fun protocol's IDL (Interface Description Language) and smart contract.

## What is Pump Fun?

Pump Fun is a fully decentralized protocol on Solana that enables the creation of tokens with built-in bonding curves. This script directly interacts with the Pump Fun smart contract (program ID: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`) using its IDL, without relying on any external APIs or centralized services.

## Technical Overview

- Direct interaction with Solana blockchain using the Pump Fun program ID
- Uses the protocol's IDL for transaction construction
- Implements the bonding curve logic directly from the smart contract
- Creates tokens with proper metadata following Metaplex standards
- Handles all necessary PDAs (Program Derived Addresses) calculations

## Features

- Create new tokens on Solana mainnet
- Direct interaction with the Pump Fun smart contract
- Automatic bonding curve setup using protocol parameters
- No reliance on external APIs (except optional IPFS for metadata)
- Full control over token creation process
- Interactive command-line interface

## Prerequisites

- Python 3.7+
- Solana CLI tools
- A Solana wallet with SOL for transaction fees
- (Optional) Pinata API keys for IPFS metadata storage

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Timaxsss/Pumpfun-Launcher.git
cd Pumpfun-Launcher
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your settings:
   - Open `create.py`
   - Replace `YOUR_PRIVATE_KEY` with your Solana private key (optional - you can enter it during runtime)
   - (Optional) Replace Pinata API keys if you want to use IPFS for metadata

## Usage

1. Run the script:
```bash
python create.py
```

2. Follow the interactive prompts:
   - Enter token name, symbol, and description
   - Choose to upload an image or use an existing URL
   - Add optional social links
   - Confirm token creation

3. The script will:
   - Calculate all necessary PDAs for the token
   - Construct the transaction using the Pump Fun IDL
   - Deploy your token directly to the Solana blockchain
   - Provide you with the mint address and bonding curve address

## Technical Details

The script works by:
1. Calculating all required PDAs (Program Derived Addresses) for the token
2. Constructing the transaction using the Pump Fun program's instruction format
3. Creating the token metadata following Metaplex standards
4. Sending the transaction directly to the Solana network
5. Setting up the bonding curve as defined in the Pump Fun protocol

## Important Notes

- The script interacts directly with the Solana blockchain and the Pump Fun smart contract
- No external APIs are required for token creation (except optional IPFS for metadata)
- All bonding curve parameters are set by the Pump Fun protocol's smart contract
- Make sure you have enough SOL in your wallet for transaction fees
- Keep your private keys secure
- Double-check all information before confirming token creation

## Support

For issues or questions, please open an issue in the GitHub repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
