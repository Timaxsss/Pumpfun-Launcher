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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default configuration
MAINNET_RPC_URL = "https://api.mainnet-beta.solana.com"
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
MPL_TOKEN_METADATA = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
RENT_SYSVAR = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

# Get API keys from environment variables
PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_SECRET_KEY = os.getenv("PINATA_SECRET_KEY")

# Remplacez ceci par votre clé privée réelle
PRIVATE_KEY = "VOTRE_CLE_PRIVEE_ICI"  # Format base58

class PumpTokenCreator:
    """
    A class to handle the creation of Pump tokens on the Solana blockchain.
    This class manages token creation, metadata handling, and IPFS uploads.
    """
    def __init__(self, private_key=None, rpc_url=None):
        """
        Initialize the PumpTokenCreator with optional private key and RPC URL.
        
        Args:
            private_key (str, optional): Base58 encoded private key
            rpc_url (str, optional): Custom RPC URL for Solana connection
        """
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
        """
        Find a Program Derived Address (PDA) based on provided seeds.
        
        Args:
            seeds (list): List of seed values
            program_id (Pubkey): Program ID to derive the address from
            
        Returns:
            tuple: (PDA address, bump seed)
        """
        seeds_bytes = [s if isinstance(s, bytes) else bytes(s) for s in seeds]
        return Pubkey.find_program_address(seeds_bytes, program_id)
    
    def get_mint_pda(self, mint_keypair):
        """
        Get all necessary PDAs for token minting.
        
        Args:
            mint_keypair (Keypair): The mint keypair
            
        Returns:
            dict: Dictionary containing all necessary PDA addresses
        """
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
        """
        Calculate the associated token account address.
        
        Args:
            owner (Pubkey): Owner's public key
            mint (Pubkey): Token mint address
            
        Returns:
            Pubkey: Associated token account address
        """
        seeds = [
            bytes(owner),
            bytes(TOKEN_PROGRAM),
            bytes(mint)
        ]
        return self.find_pda(seeds, ASSOCIATED_TOKEN_PROGRAM)[0]
    
    def get_fee_recipient(self):
        """
        Retrieve the fee recipient address from the global state.
        
        Returns:
            Pubkey: Fee recipient address or None if not found
        """
        try:
            global_seed = b"global"
            global_key, _ = self.find_pda([global_seed], PUMP_PROGRAM_ID)
            
            # RPC call to get account data
            response = self.client.get_account_info(global_key)
            if response.value is None:
                print("Unable to retrieve global state.")
                return None
            
            # Account data starts with an 8-byte discriminator, followed by the structure
            # Global structure: initialized (bool), authority (pubkey), feeRecipient (pubkey), ...
            # bool = 1 byte, pubkey = 32 bytes
            # feeRecipient starts at offset 8 (discriminator) + 1 (initialized) + 32 (authority) = 41
            account_data = response.value.data
            if len(account_data) < 73:  # 8 + 1 + 32 + 32
                print("Invalid global account data.")
                return None
            
            # Extract fee recipient address
            fee_recipient_bytes = account_data[41:73]
            fee_recipient = Pubkey(fee_recipient_bytes)
            return fee_recipient
        except Exception as e:
            print(f"Error retrieving fee recipient: {str(e)}")
            return None
    
    def create_token_with_buy(self, name, symbol, uri, dev_buy_amount, creator=None):
        """
        Create a new token and optionally perform an initial buy.
        
        Args:
            name (str): Token name
            symbol (str): Token symbol
            uri (str): Metadata URI
            dev_buy_amount (float): Amount of SOL to spend on initial buy
            creator (Pubkey, optional): Creator's public key
            
        Returns:
            tuple: (mint address, transaction signature)
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Default creator is the wallet owner
                if creator is None:
                    creator = self.public_key
                else:
                    creator = Pubkey.from_string(creator)
                    
                # Create mint keypair
                mint_keypair = Keypair()
                print(f"New mint address created: {mint_keypair.pubkey()}")
                
                # Get necessary PDAs
                pdas = self.get_mint_pda(mint_keypair)
                
                # Find associated token account for bonding curve
                associated_bonding_curve = self.get_associated_token_address(
                    pdas["bonding_curve"],
                    mint_keypair.pubkey()
                )
                
                # Find associated token account for user
                associated_user = self.get_associated_token_address(
                    self.public_key,
                    mint_keypair.pubkey()
                )
                
                # Get fee recipient
                fee_recipient = self.get_fee_recipient()
                if not fee_recipient:
                    fee_recipient = EVENT_AUTHORITY
                    print(f"Using event authority as fee recipient: {fee_recipient}")
                else:
                    print(f"Fee recipient retrieved: {fee_recipient}")
                
                # Construct creation instruction
                create_ix_data = bytes([24, 30, 200, 40, 5, 28, 7, 119])
                name_bytes = name.encode('utf-8')
                symbol_bytes = symbol.encode('utf-8')
                uri_bytes = uri.encode('utf-8')
                
                create_ix_data += len(name_bytes).to_bytes(4, byteorder='little')
                create_ix_data += name_bytes
                create_ix_data += len(symbol_bytes).to_bytes(4, byteorder='little')
                create_ix_data += symbol_bytes
                create_ix_data += len(uri_bytes).to_bytes(4, byteorder='little')
                create_ix_data += uri_bytes
                create_ix_data += bytes(creator)
                
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
                
                create_ix = Instruction(
                    program_id=PUMP_PROGRAM_ID,
                    accounts=create_accounts,
                    data=create_ix_data
                )
                
                # List of instructions
                instructions = [create_ix]
                
                if dev_buy_amount > 0:
                    # Add instruction to create user ATA
                    ata_ix_data = bytes([])  # No data needed for create_associated_token_account
                    ata_accounts = [
                        AccountMeta(pubkey=self.public_key, is_signer=True, is_writable=True),  # Payer
                        AccountMeta(pubkey=associated_user, is_signer=False, is_writable=True),  # ATA
                        AccountMeta(pubkey=self.public_key, is_signer=False, is_writable=False),  # Owner
                        AccountMeta(pubkey=mint_keypair.pubkey(), is_signer=False, is_writable=False),  # Mint
                        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=RENT_SYSVAR, is_signer=False, is_writable=False),
                    ]
                    
                    ata_ix = Instruction(
                        program_id=ASSOCIATED_TOKEN_PROGRAM,
                        accounts=ata_accounts,
                        data=ata_ix_data
                    )
                    
                    instructions.append(ata_ix)
                    
                    # Construct buy instruction
                    buy_ix_data = bytes([102, 6, 61, 18, 1, 218, 235, 234])
                    buy_amount = 1_000_000  # Adjust for 1 token with 6 decimals (e.g.)
                    max_sol_cost = int(dev_buy_amount * 1_000_000_000)  # Conversion to lamports
                    
                    buy_ix_data += buy_amount.to_bytes(8, byteorder='little')
                    buy_ix_data += max_sol_cost.to_bytes(8, byteorder='little')
                    
                    buy_accounts = [
                        AccountMeta(pubkey=pdas["global"], is_signer=False, is_writable=False),
                        AccountMeta(pubkey=fee_recipient, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=mint_keypair.pubkey(), is_signer=False, is_writable=False),
                        AccountMeta(pubkey=pdas["bonding_curve"], is_signer=False, is_writable=True),
                        AccountMeta(pubkey=associated_bonding_curve, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=associated_user, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=self.public_key, is_signer=True, is_writable=True),
                        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=RENT_SYSVAR, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=PUMP_PROGRAM_ID, is_signer=False, is_writable=False),
                    ]
                    
                    buy_ix = Instruction(
                        program_id=PUMP_PROGRAM_ID,
                        accounts=buy_accounts,
                        data=buy_ix_data
                    )
                    
                    instructions.append(buy_ix)
                
                # Get new blockhash
                blockhash_resp = self.client.get_latest_blockhash()
                blockhash = blockhash_resp.value.blockhash
                
                # Construct transaction message
                message = Message(instructions, self.public_key)
                
                # Construct transaction
                tx = Transaction(
                    [self.keypair, mint_keypair], 
                    message, 
                    blockhash
                )
                
                # Serialize and send transaction
                try:
                    # Use bytes() to serialize the transaction
                    serialized_tx = bytes(tx)
                    result = self.client.send_raw_transaction(serialized_tx)
                    
                    print(f"Transaction submitted: {result.value}")
                    return {
                        "success": True,
                        "mint": str(mint_keypair.pubkey()),
                        "tx_signature": result.value,
                        "bonding_curve": str(pdas["bonding_curve"]),
                        "dev_buy_amount": dev_buy_amount if dev_buy_amount > 0 else 0
                    }
                except Exception as e:
                    print(f"Error during transaction serialization: {str(e)}")
                    return {"success": False, "error": str(e)}
                
            except Exception as e:
                error_str = str(e)
                if "Blockhash not found" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Attempt {retry_count + 1} out of {max_retries}...")
                        time.sleep(1)
                        continue
                print(f"Error creating token: {error_str}")
                return {"success": False, "error": error_str}
        
        return {"success": False, "error": "Maximum number of attempts reached"}


def upload_to_ipfs(image_path):
    """Upload an image to IPFS via Pinata"""
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
    print("=== Pump Token Creator ===")
    
    # Check if using default key or ask for a new one
    use_default_key = PRIVATE_KEY != "VOTRE_CLE_PRIVEE_ICI"
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
    print("1. Use a local image (will be uploaded to IPFS)")
    print("2. Use an image URL")
    image_choice = input("Choose an option (1 or 2): ")
    
    image_uri = None
    if image_choice == "1":
        image_path = input("Image file name (ex: image.png): ")
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
    
    # Ask for initial dev buy amount
    dev_buy_amount = 0
    try:
        dev_buy_input = input("\nInitial dev buy amount in SOL (leave empty or 0 for none): ")
        if dev_buy_input.strip():
            dev_buy_amount = float(dev_buy_input)
            if dev_buy_amount < 0:
                print("Amount cannot be negative. Setting to 0.")
                dev_buy_amount = 0
    except ValueError:
        print("Invalid amount. Setting to 0.")
        dev_buy_amount = 0
    
    # Create metadata in Metaplex format
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
        print("Failed to upload metadata. Using data URI as fallback.")
        # Use a data URI as fallback solution
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
    print(f"Initial dev buy: {dev_buy_amount if dev_buy_amount > 0 else 'None'} SOL")
    
    confirm = input("\nConfirm token creation? (y/n): ")
    if confirm.lower() != 'y':
        print("Creation cancelled")
        return
    
    # Create token with optional initial buy
    print("\nCreating token...")
    result = creator.create_token_with_buy(name, symbol, metadata_uri, dev_buy_amount, creator_address)
    
    if result["success"]:
        print("\n=== Token creation successful! ===")
        print(f"Mint address: {result['mint']}")
        print(f"Transaction signature: {result['tx_signature']}")
        print(f"Bonding curve address: {result['bonding_curve']}")
        if result.get("dev_buy_amount", 0) > 0:
            print(f"Initial dev buy: {result['dev_buy_amount']} SOL")
        print("\nToken is now available on the blockchain!")
    else:
        print("\n=== Token creation failed ===")
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    interactive_token_creation()