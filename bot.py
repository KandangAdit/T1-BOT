from web3 import Web3
from eth_utils import keccak, to_hex
from eth_abi.abi import encode
from eth_account import Account
from aiohttp import ClientSession, ClientTimeout
from datetime import datetime
from colorama import *
import asyncio, json, random, time, os, pytz, configparser

wib = pytz.timezone('Asia/Jakarta')

class TOne:
    def __init__(self) -> None:
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.ARB_SEPOLIA = { 
            "Ticker": "ARB Sepolia", 
            "ChainId": 421614, 
            "RPC": "https://orbital-red-yard.arbitrum-sepolia.quiknode.pro/c41a8b649724b6ca9ee30e159fd273dde85e31b5", 
            "Explorer": "https://sepolia.arbiscan.io/tx",
            "Router Address": "0x4727D2EC7b602628980BE1E1a4e99d39A45786A4"
        }
        self.BASE_SEPOLIA = { 
            "Ticker": "Base Sepolia", 
            "ChainId": 84532, 
            "RPC": "https://smart-fabled-tab.base-sepolia.quiknode.pro/d88230d32fbb535dcd278e6c42da494ee1e464c7", 
            "Explorer": "https://sepolia.basescan.org/tx",
            "Router Address": "0xf96B8CcB029E0932fe36da0CeDd2b035E2c1695d" 
        }
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]}
        ]''')
        self.BRIDGE_CONTRACT_ABI = [
            {
                "inputs": [
                    {
                        "components": [
                            { "internalType": "uint32", "name": "fillDeadline", "type": "uint32" },
                            { "internalType": "bytes32", "name": "orderDataType", "type": "bytes32" },
                            { "internalType": "bytes", "name": "orderData", "type": "bytes" }
                        ],
                        "internalType": "struct Order",
                        "name": "_order",
                        "type": "tuple"
                    }
                ],
                "name": "open",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.bridge_count = self.config.getint('main', 'bridge_count')
        self.arb_amount = self.config.getfloat('bridge', 'arb_amount')
        self.base_SEPOLIA_amount = self.config.getfloat('bridge', 'base_amount')
        self.min_delay = self.config.getint('main', 'min_delay')
        self.max_delay = self.config.getint('main', 'max_delay')

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}T1 Protocol{Fore.BLUE + Style.BRIGHT} Auto BOT
            """
            f"""
        {Fore.GREEN + Style.BRIGHT}Rey? {Fore.YELLOW + Style.BRIGHT}<INI WATERMARK>
            """
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    
    async def load_proxies(self, use_proxy_choice: int):
        filename = "proxy.txt"
        try:
            if use_proxy_choice == 1:
                async with ClientSession(timeout=ClientTimeout(total=30)) as session:
                    async with session.get("https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/main/http.txt") as response:
                        response.raise_for_status()
                        content = await response.text()
                        with open(filename, 'w') as f:
                            f.write(content)
                        self.proxies = [line.strip() for line in content.splitlines() if line.strip()]
            else:
                if not os.path.exists(filename):
                    self.log(f"{Fore.RED + Style.BRIGHT}File {filename} Not Found.{Style.RESET_ALL}")
                    return
                with open(filename, 'r') as f:
                    self.proxies = [line.strip() for line in f.read().splitlines() if line.strip()]
            
            if not self.proxies:
                self.log(f"{Fore.RED + Style.BRIGHT}No Proxies Found.{Style.RESET_ALL}")
                return

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Proxies Total  : {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(self.proxies)}{Style.RESET_ALL}"
            )
        
        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Failed To Load Proxies: {e}{Style.RESET_ALL}")
            self.proxies = []

    def check_proxy_schemes(self, proxies):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxies.startswith(scheme) for scheme in schemes):
            return proxies
        return f"http://{proxies}"

    def get_next_proxy_for_account(self, token):
        if token not in self.account_proxies:
            if not self.proxies:
                return None
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[token] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[token]

    def rotate_proxy_for_account(self, token):
        if not self.proxies:
            return None
        proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
        self.account_proxies[token] = proxy
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy
    
    def generate_address(self, account: str):
        try:
            account = Account.from_key(account)
            address = account.address
            
            return address
        except Exception as e:
            return None
        
    def mask_account(self, account):
        try:
            mask_account = account[:6] + '*' * 6 + account[-6:]
            return mask_account
        except Exception as e:
            return None
        
    async def get_web3_with_check(self, address: str, option: str, use_proxy: bool, retries=3, timeout=60):
        request_kwargs = {"timeout": timeout}

        proxy = self.get_next_proxy_for_account(address) if use_proxy else None

        if use_proxy and proxy:
            request_kwargs["proxies"] = {"http": proxy, "https": proxy}

        if option == "Arbitrum to Base":
            rpc_url = self.ARB_SEPOLIA["RPC"]

        elif option == "Base to Arbitrum":
            rpc_url = self.BASE_SEPOLIA["RPC"]

        for attempt in range(retries):
            try:
                web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs=request_kwargs))
                web3.eth.get_block_number()
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                raise Exception(f"Failed to Connect to RPC: {str(e)}")
        
    async def get_token_balance(self, address: str, option: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, option, use_proxy)
            balance = web3.eth.get_balance(address)

            token_balance = balance / (10 ** 18)

            return token_balance
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None
        
    async def perform_bridge(self, account: str, address: str, option: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, option, use_proxy)

            if option == "Arbitrum to Base":
                bridge_amount = self.arb_amount
                original_domain = self.ARB_SEPOLIA["ChainId"]
                destination_domain = self.BASE_SEPOLIA["ChainId"]
                original_settler = self.ARB_SEPOLIA["Router Address"]
                destination_settler = self.BASE_SEPOLIA["Router Address"]

            elif option == "Base to Arbitrum":
                bridge_amount = self.base_SEPOLIA_amount
                original_domain = self.BASE_SEPOLIA["ChainId"]
                destination_domain = self.ARB_SEPOLIA["ChainId"]
                original_settler = self.BASE_SEPOLIA["Router Address"]
                destination_settler = self.ARB_SEPOLIA["Router Address"]

            token_contract = web3.eth.contract(address=web3.to_checksum_address(original_settler), abi=self.BRIDGE_CONTRACT_ABI)

            amount_in = web3.to_wei(bridge_amount, "ether")
            fees_to_wei = int(amount_in * 0.0001)
            amount_out = amount_in - fees_to_wei
            sender_nonce = random.randint(10**15, 10**16 - 1)
            deadline = int(time.time() + 3000)

            order_data_type = to_hex(keccak(text=(
                "OrderData("
                "bytes32 sender,"
                "bytes32 recipient,"
                "bytes32 inputToken,"
                "bytes32 outputToken,"
                "uint256 amountIn,"
                "uint256 amountOut,"
                "uint256 senderNonce,"
                "uint32 originDomain,"
                "uint32 destinationDomain,"
                "bytes32 destinationSettler,"
                "uint32 fillDeadline,"
                "bytes data)"
            )))

            order_data_bytes = encode(
                [
                    "bytes32", "bytes32", "bytes32", "bytes32", 
                    "uint256", "uint256", "uint256", "uint32", 
                    "uint32", "bytes32", "uint32", "bytes"
                ],
                [

                    web3.to_bytes(hexstr=address).rjust(32, b'\x00'),
                    web3.to_bytes(hexstr=address).rjust(32, b'\x00'),
                    b"\x00" * 32,
                    b"\x00" * 32,
                    amount_in,
                    amount_out,
                    sender_nonce,
                    original_domain,
                    destination_domain,
                    web3.to_bytes(hexstr=destination_settler).rjust(32, b'\x00'),
                    deadline,
                    b""
                ]
            )

            order_data_hex = to_hex(order_data_bytes)[2:]
            offset = hex(32)[2:].zfill(64)
            final_data_bytes = bytes.fromhex(offset + order_data_hex)
            order_data = to_hex(final_data_bytes)

            _order = (
                deadline,
                order_data_type,
                order_data
            )
           
            bridge_data = token_contract.functions.open(_order)

            estimated_gas = bridge_data.estimate_gas({"from": address, "value":amount_in})
            latest_block = web3.eth.get_block("latest")
            base_fee = latest_block.get("baseFeePerGas", 0)
            max_priority_fee = base_fee * 2
            max_fee = max_priority_fee

            bridge_tx = bridge_data.build_transaction({
                "from": address,
                "value": int(amount_in),
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": original_domain,
            })

            signed_tx = web3.eth.account.sign_transaction(bridge_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await asyncio.to_thread(web3.eth.wait_for_transaction_receipt, tx_hash, timeout=300)
            block_number = receipt.blockNumber

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def print_timer(self):
        for remaining in range(random.randint(self.min_delay, self.max_delay), 0, -1):
            print(
                f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Wait For{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {remaining} {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Seconds For Next Tx...{Style.RESET_ALL}",
                end="\r",
                flush=True
            )
            await asyncio.sleep(1)
        
    async def process_perform_bridge(self, account: str, address: str, option: str, use_proxy: bool):
        if option == "Arbitrum to Base":
            explorer = self.ARB_SEPOLIA["Explorer"]

        elif option == "Base to Arbitrum":
            explorer = self.BASE_SEPOLIA["Explorer"]

        tx_hash, block_number = await self.perform_bridge(account, address, option, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer:{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {explorer}/{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_option_1(self, account: str, address: str, use_proxy: bool):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Bridge    :{Style.RESET_ALL}")

        for i in range(self.bridge_count):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{i+1}{Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT} Of {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{self.bridge_count}{Style.RESET_ALL}                                   "
            )

            option = "Arbitrum to Base"
            ticker = self.ARB_SEPOLIA["Ticker"]
            amount = self.arb_amount

            balance = await self.get_token_balance(address, option, use_proxy)

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Option  :{Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT} {option} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} {ticker} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {amount} {ticker} {Style.RESET_ALL}"
            )

            if not balance or balance <= amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient {ticker} Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_bridge(account, address, option, use_proxy)
            await self.print_timer()

    async def process_option_2(self, account: str, address: str, use_proxy: bool):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Bridge    :{Style.RESET_ALL}")

        for i in range(self.bridge_count):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{i+1}{Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT} Of {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{self.bridge_count}{Style.RESET_ALL}                                   "
            )

            option = "Base to Arbitrum"
            ticker = self.BASE_SEPOLIA["Ticker"]
            amount = self.base_SEPOLIA_amount

            balance = await self.get_token_balance(address, option, use_proxy)

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Option  :{Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT} {option} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} {ticker} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {amount} {ticker} {Style.RESET_ALL}"
            )

            if not balance or balance <= amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient {ticker} Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_bridge(account, address, option, use_proxy)
            await self.print_timer()

    async def process_option_3(self, account: str, address: str, use_proxy: bool):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Bridge    :{Style.RESET_ALL}")

        for i in range(self.bridge_count):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{i+1}{Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT} Of {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT}{self.bridge_count}{Style.RESET_ALL}                                   "
            )

            option = random.choice(["Arbitrum to Base", "Base to Arbitrum"])

            if option == "Arbitrum to Base":
                ticker = self.ARB_SEPOLIA["Ticker"]
                amount = self.arb_amount

            elif option == "Base to Arbitrum":
                ticker = self.BASE_SEPOLIA["Ticker"]
                amount = self.base_SEPOLIA_amount

            balance = await self.get_token_balance(address, option, use_proxy)

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Option  :{Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT} {option} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} {ticker} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {amount} {ticker} {Style.RESET_ALL}"
            )

            if not balance or balance <= amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient {ticker} Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_bridge(account, address, option, use_proxy)
            await self.print_timer()

    async def process_accounts(self, account: str, address: str, option: str, use_proxy: bool):
        proxy = self.get_next_proxy_for_account(address) if use_proxy else None
        self.log(
            f"{Fore.CYAN + Style.BRIGHT}Proxy     :{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {proxy} {Style.RESET_ALL}"
        )

        if option == 1:
            await self.process_option_1(account, address, use_proxy)

        elif option == 2:
            await self.process_option_2(account, address, use_proxy)

        elif option == 3:
            await self.process_option_3(account, address, use_proxy)

    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]

            option = self.config.getint('main', 'option')
            use_proxy_choice = self.config.getint('proxy', 'use_proxy')

            use_proxy = False
            if use_proxy_choice in [1, 2]:
                use_proxy = True

            while True:
                self.clear_terminal()
                self.welcome()
                self.log(
                    f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
                )

                if use_proxy:
                    await self.load_proxies(use_proxy_choice)
                
                separator = "=" * 25
                for account in accounts:
                    if account:
                        address = self.generate_address(account)

                        self.log(
                            f"{Fore.CYAN + Style.BRIGHT}{separator}[{Style.RESET_ALL}"
                            f"{Fore.WHITE + Style.BRIGHT} {self.mask_account(address)} {Style.RESET_ALL}"
                            f"{Fore.CYAN + Style.BRIGHT}]{separator}{Style.RESET_ALL}"
                        )

                        if not address:
                            self.log(
                                f"{Fore.CYAN + Style.BRIGHT}Status    :{Style.RESET_ALL}"
                                f"{Fore.RED + Style.BRIGHT} Invalid Private Key or Library Version Not Supported {Style.RESET_ALL}"
                            )
                            continue

                        await self.process_accounts(account, address, option, use_proxy_choice)
                        await asyncio.sleep(3)

                self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*72)
                seconds = 24 * 60 * 60
                while seconds > 0:
                    formatted_time = self.format_seconds(seconds)
                    print(
                        f"{Fore.CYAN+Style.BRIGHT}[ Wait for{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {formatted_time} {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT}... ]{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} | {Style.RESET_ALL}"
                        f"{Fore.BLUE+Style.BRIGHT}All Accounts Have Been Processed.{Style.RESET_ALL}",
                        end="\r"
                    )
                    await asyncio.sleep(1)
                    seconds -= 1

        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'accounts.txt' Not Found.{Style.RESET_ALL}")
            return
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")
            raise e

if __name__ == "__main__":
    try:
        bot = TOne()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] T1 Protocol - BOT{Style.RESET_ALL}                                       "                              
        )