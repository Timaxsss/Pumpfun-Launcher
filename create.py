import json
import base58
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
import struct
import time
import os
import base64
from PIL import Image
import io
import requests

# Default configuration
MAINNET_RPC_URL = "https://api.mainnet-beta.solana.com"
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
MPL_TOKEN_METADATA = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
RENT_SYSVAR = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

# Replace with your own API keys
PINATA_API_KEY = "YOUR_PINATA_API_KEY"
PINATA_SECRET_KEY = "YOUR_PINATA_SECRET_KEY"

# Replace with your private key
PRIVATE_KEY = "YOUR_PRIVATE_KEY"  # base58 format

class PumpTokenCreator:
    def __init__(self, private_key=None, rpc_url=None):
        self.rpc_url = rpc_url or MAINNET_RPC_URL
        self.client = Client(self.rpc_url)
        
        # Initialize keypair
        if private_key:
            decoded_key = base58.b58decode(private_key)
            self.keypair = Keypair.from_bytes(decoded_key)
        else:
            print("No private key provided, generating a new key...")
            self.keypair = Keypair()
        
        self.public_key = self.keypair.pubkey()
        print(f"Using address: {self.public_key}")
    
    @staticmethod
    def find_pda(seeds, program_id):
        """Find a PDA (Program Derived Address) based on seeds"""
        seeds_bytes = [s if isinstance(s, bytes) else bytes(s) for s in seeds]
        return Pubkey.find_program_address(seeds_bytes, program_id)
    
    def get_mint_pda(self, mint_keypair):
        global_seed = b"global"
        global_key, _ = self.find_pda([global_seed], PUMP_PROGRAM_ID)
        
        bonding_curve_seed = b"bonding-curve"
        bonding_curve_key, _ = self.find_pda(
            [bonding_curve_seed, bytes(mint_keypair.pubkey())], 
            PUMP_PROGRAM_ID
        )
        
        mint_authority_seed = b"mint-authority"
        mint_authority_key, _ = self.find_pda(
            [mint_authority_seed], 
            PUMP_PROGRAM_ID
        )
        
        # Derive metadata address
        seeds = bytes([109, 101, 116, 97, 100, 97, 116, 97])  # "metadata" in bytes
        metadata_key, _ = self.find_pda(
            [seeds, bytes(MPL_TOKEN_METADATA), bytes(mint_keypair.pubkey())],
            MPL_TOKEN_METADATA
        )
        
        return {
            "global": global_key,
            "bonding_curve": bonding_curve_key,
            "mint_authority": mint_authority_key,
            "metadata": metadata_key
        }
    
    def get_associated_token_address(self, owner, mint):
        """Calculate associated token address"""
        # Simplified implementation based on Solana logic
        seeds = [
            bytes(owner),
            bytes(TOKEN_PROGRAM),
            bytes(mint)
        ]
        return self.find_pda(seeds, ASSOCIATED_TOKEN_PROGRAM)[0]
    
    def create_token(self, name, symbol, uri, creator=None):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Default creator is the wallet owner
                if creator is None:
                    creator = self.public_key
                else:
                    creator = Pubkey.from_string(creator)
                    
                # Create a keypair for the mint
                mint_keypair = Keypair()
                print(f"New mint address created: {mint_keypair.pubkey()}")
                
                # Get required PDAs
                pdas = self.get_mint_pda(mint_keypair)
                
                # Find associated token account for bonding curve
                associated_bonding_curve = self.get_associated_token_address(
                    pdas["bonding_curve"],
                    mint_keypair.pubkey()
                )
                
                # Build creation instruction
                # discriminator for "create" [24, 30, 200, 40, 5, 28, 7, 119]
                create_ix_data = bytes([24, 30, 200, 40, 5, 28, 7, 119])
                
                # Add arguments according to IDL structure
                name_bytes = name.encode('utf-8')
                symbol_bytes = symbol.encode('utf-8')
                uri_bytes = uri.encode('utf-8')
                
                # Format arguments for create instruction
                # Length then data for each string, then creator public key
                # Note: Follow exact structure defined in IDL
                create_ix_data += len(name_bytes).to_bytes(4, byteorder='little')
                create_ix_data += name_bytes
                create_ix_data += len(symbol_bytes).to_bytes(4, byteorder='little')
                create_ix_data += symbol_bytes
                create_ix_data += len(uri_bytes).to_bytes(4, byteorder='little')
                create_ix_data += uri_bytes
                create_ix_data += bytes(creator)
                
                # Create AccountMeta for instruction
                create_accounts = [
                    AccountMeta(pubkey=mint_keypair.pubkey(), is_signer=True, is_writable=True),
                    AccountMeta(pubkey=pdas["mint_authority"], is_signer=False, is_writable=False),
                    AccountMeta(pubkey=pdas["bonding_curve"], is_signer=False, is_writable=True),
                    AccountMeta(pubkey=associated_bonding_curve, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=pdas["global"], is_signer=False, is_writable=False),
                    AccountMeta(pubkey=MPL_TOKEN_METADATA, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=pdas["metadata"], is_signer=False, is_writable=True),
                    AccountMeta(pubkey=self.public_key, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=ASSOCIATED_TOKEN_PROGRAM, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=RENT_SYSVAR, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=PUMP_PROGRAM_ID, is_signer=False, is_writable=False),
                ]
                
                # Create instruction
                create_ix = Instruction(
                    program_id=PUMP_PROGRAM_ID,
                    accounts=create_accounts,
                    data=create_ix_data
                )
                
                # Get new blockhash just before sending transaction
                blockhash_resp = self.client.get_latest_blockhash()
                blockhash = blockhash_resp.value.blockhash
                
                # Create transaction message
                message = Message([create_ix], self.public_key)
                
                # Create transaction with message, signers and blockhash
                tx = Transaction(
                    [self.keypair, mint_keypair], 
                    message, 
                    blockhash
                )
                
                try:
                    # Serialize and send transaction
                    if hasattr(tx, 'serialize'):
                        serialized_tx = tx.serialize()
                    else:
                        serialized_tx = bytes(tx)
                        
                    result = self.client.send_raw_transaction(serialized_tx)
                    
                    print(f"Transaction submitted: {result.value}")
                    return {
                        "success": True,
                        "mint": str(mint_keypair.pubkey()),
                        "tx_signature": result.value,
                        "bonding_curve": str(pdas["bonding_curve"])
                    }
                except AttributeError as e:
                    print("Error: Unable to serialize transaction. Check your solders library version.")
                    print(f"Error details: {str(e)}")
                    return {"success": False, "error": str(e)}
                
            except Exception as e:
                error_str = str(e)
                if "Blockhash not found" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Attempt {retry_count + 1} of {max_retries}...")
                        time.sleep(1)  # Wait before retrying
                        continue
                print(f"Error creating token: {error_str}")
                return {"success": False, "error": error_str}
        
        return {"success": False, "error": "Maximum number of attempts reached"}

def upload_to_ipfs(image_path):
    """Upload image to IPFS via Pinata"""
    try:
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        
        with open(image_path, 'rb') as img_file:
            files = {'file': (os.path.basename(image_path), img_file)}
            headers = {
                'pinata_api_key': PINATA_API_KEY,
                'pinata_secret_api_key': PINATA_SECRET_KEY
            }
            
            response = requests.post(url, files=files, headers=headers)
            if response.status_code == 200:
                ipfs_hash = response.json()['IpfsHash']
                return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
            else:
                print(f"Error uploading to IPFS: {response.text}")
                return None
    except Exception as e:
        print(f"Error uploading to IPFS: {str(e)}")
        return None

def upload_metadata_to_ipfs(metadata):
    """Upload metadata to IPFS via Pinata"""
    try:
        url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
        
        headers = {
            'Content-Type': 'application/json',
            'pinata_api_key': PINATA_API_KEY,
            'pinata_secret_api_key': PINATA_SECRET_KEY
        }
        
        response = requests.post(url, json=metadata, headers=headers)
        if response.status_code == 200:
            ipfs_hash = response.json()['IpfsHash']
            return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
        else:
            print(f"Error uploading metadata to IPFS: {response.text}")
            return None
    except Exception as e:
        print(f"Error uploading metadata to IPFS: {str(e)}")
        return None

def interactive_token_creation():
    print("=== Pump Fun Token Creator ===")
    
    # Check if using default key or request a new one
    use_default_key = PRIVATE_KEY != "YOUR_PRIVATE_KEY"
    private_key = PRIVATE_KEY
    
    if not use_default_key:
        key_input = input("Enter your private key (leave empty to generate a new one): ")
        if key_input.strip():
            private_key = key_input
    
    # Create PumpTokenCreator instance
    creator = PumpTokenCreator(private_key=private_key)
    
    # Collect token information
    print("\nEnter information for your new token:")
    name = input("Token name: ")
    symbol = input("Token symbol: ")
    description = input("Token description: ")
    
    # Image handling
    print("\nImage handling:")
    print("1. Use local image (will be uploaded to IPFS)")
    print("2. Use image URL")
    image_choice = input("Choose an option (1 or 2): ")
    
    image_uri = None
    if image_choice == "1":
        image_path = input("Image filename (e.g. image.png): ")
        if os.path.exists(image_path):
            print("\nUploading image to IPFS...")
            image_uri = upload_to_ipfs(image_path)
            
            if not image_uri:
                print("Upload failed. Please use a URL instead.")
                image_uri = input("Image URL: ")
        else:
            print(f"File {image_path} does not exist. Please use a URL instead.")
            image_uri = input("Image URL: ")
    else:
        image_uri = input("Image URL: ")
    
    if not image_uri:
        print("Error: No image provided.")
        return
    
    # Ask for social links
    print("\nSocial links (optional):")
    telegram = input("Telegram link (leave empty if none): ")
    website = input("Website (leave empty if none): ")
    twitter = input("Twitter link (leave empty if none): ")
    
    # Create Metaplex format metadata
    metadata = {
        "name": name,
        "symbol": symbol,
        "description": description,
        "image": image_uri,
        "attributes": [],
        "properties": {
            "files": [{"uri": image_uri, "type": "image/png"}],
            "category": "image"
        }
    }
    
    # Add social links only if provided
    if telegram or website or twitter:
        metadata["properties"]["links"] = {}
        
        if telegram:
            metadata["properties"]["links"]["telegram"] = telegram
        if website:
            metadata["properties"]["links"]["website"] = website
        if twitter:
            metadata["properties"]["links"]["twitter"] = twitter
    
    # Upload metadata to IPFS (recommended solution)
    print("\nUploading metadata to IPFS...")
    metadata_uri = upload_metadata_to_ipfs(metadata)
    
    if not metadata_uri:
        print("Metadata upload failed. Using data URI instead.")
        # Use data URI as fallback
        metadata_json = json.dumps(metadata)
        metadata_uri = f"data:application/json;base64,{base64.b64encode(metadata_json.encode()).decode()}"
    
    creator_input = input("Creator address (leave empty to use your address): ")
    creator_address = creator_input if creator_input.strip() else None
    
    # Confirmation
    print("\nSummary:")
    print(f"Name: {name}")
    print(f"Symbol: {symbol}")
    print(f"Description: {description}")
    print(f"Image: {image_uri}")
    print(f"Metadata URI: {metadata_uri}")
    print(f"Telegram: {telegram if telegram else 'Not specified'}")
    print(f"Website: {website if website else 'Not specified'}")
    print(f"Twitter: {twitter if twitter else 'Not specified'}")
    print(f"Creator: {creator_address if creator_address else creator.public_key}")
    
    confirm = input("\nConfirm token creation? (y/n): ")
    if confirm.lower() != 'y':
        print("Creation cancelled")
        return
    
    # Create token
    print("\nCreating token...")
    result = creator.create_token(name, symbol, metadata_uri, creator_address)
    
    if result["success"]:
        print("\n=== Token creation successful! ===")
        print(f"Mint address: {result['mint']}")
        print(f"Transaction signature: {result['tx_signature']}")
        print(f"Bonding curve address: {result['bonding_curve']}")
        print("\nToken is now available on the blockchain!")
    else:
        print("\n=== Token creation failed ===")
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    interactive_token_creation()