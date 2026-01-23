from playwright.async_api import async_playwright
import asyncio
import dotenv
import os
import base64
from solders.keypair import Keypair

dotenv.load_dotenv()

with open("ethers.min.js", "r") as f:
    ETHERS_JS = f.read()

with open("solana.min.js", "r") as f:
    SOLANA_JS = f.read()


def get_ethereum_provider(pk: str, rpc="https://bsc-dataseed.binance.org/", chain_id="0x38"):
    return (
        """
(() => {
  const provider = new ethers.providers.JsonRpcProvider(
    "__RPC__"
  );
  const wallet = new ethers.Wallet("__PK__", provider);

  const listeners = {};

  window.ethereum = {
    isMetaMask: true,
    isConnected: () => true,
    selectedAddress: wallet.address,
    chainId: "__CHAIN_ID__",

    request: async ({ method, params = [] }) => {
      switch (method) {
        case "eth_accounts":
        case "eth_requestAccounts":
          return [wallet.address];

        case "eth_chainId":
          return "0x1";

        case "personal_sign":
          return wallet.signMessage(
            ethers.utils.arrayify(params[0])
          );

        case "eth_signTypedData_v4": {
          const typedData = JSON.parse(params[1]);
          return wallet._signTypedData(
            typedData.domain,
            typedData.types,
            typedData.message
          );
        }

        case "eth_sendTransaction":
          return (await wallet.sendTransaction(params[0])).hash;

        case "eth_estimateGas":
          return provider.estimateGas(params[0]);

        case "eth_getBalance":
          return provider.getBalance(params[0]);

        default:
          throw new Error("Unsupported method " + method);
      }
    },

    on: (event, cb) => {
      listeners[event] = listeners[event] || [];
      listeners[event].push(cb);
    },

    removeListener: () => {}
  };

  window.dispatchEvent(new Event("ethereum#initialized"));
})();
""".replace(
            "__PK__", pk
        )
        .replace("__RPC__", rpc)
        .replace("__CHAIN_ID__", chain_id)
    )


def get_solana_provider(pk_b64: str):
    return """
(() => {
  const Solana = window.solanaWeb3 || window.SolanaWeb3;
  if (!Solana?.Keypair) throw new Error("Solana SDK missing");

  const secretKey = Uint8Array.from(atob("__PK__"), c => c.charCodeAt(0));
  if (secretKey.length !== 64) throw new Error("Bad key length");

  const keypair = Solana.Keypair.fromSecretKey(secretKey);

  const listeners = { connect: [], accountChanged: [] };

  function emit(event, payload) {
    (listeners[event] || []).forEach(fn => fn(payload));
  }

  window.solana = {
    isPhantom: true,
    publicKey: keypair.publicKey,
    isConnected: false,

    connect: async (opts = {}) => {
      window.solana.isConnected = true;
      emit("connect", keypair.publicKey);
      emit("accountChanged", keypair.publicKey);
      return { publicKey: keypair.publicKey };
    },

    disconnect: async () => {
      window.solana.isConnected = false;
    },

    signMessage: async (msg) => {
      const data = msg instanceof Uint8Array ? msg : new TextEncoder().encode(msg);
      const sig = Solana.nacl.sign.detached(data, keypair.secretKey);
      return { signature: sig, publicKey: keypair.publicKey };
    },

    on: (event, fn) => {
      listeners[event] = listeners[event] || [];
      listeners[event].push(fn);
    },

    off: () => {}
  };

  // 🔥 AUTO-CONNECT AS PHANTOM DOES
  setTimeout(() => {
    window.solana.connect({ onlyIfTrusted: true });
  }, 0);

})();
""".replace(
        "__PK__", pk_b64
    )


async def connect_metamask():
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("PRIVATE_KEY missing in .env")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            bypass_csp=True,
            viewport={"width": 1280, "height": 800},
        )

        # 1️⃣ Inject ethers synchronously
        await context.add_init_script(ETHERS_JS)

        # 2️⃣ Inject ethereum provider
        await context.add_init_script(get_ethereum_provider(private_key))

        page = await context.new_page()

        # 3️⃣ Navigate
        await page.goto(
            "https://pancakeswap.finance/swap",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_function("() => window.ethereum && window.ethereum.chainId === '0x38'")

        address = await page.evaluate("() => window.ethereum.selectedAddress")

        print("✅ Connected address:", address)

        await page.wait_for_timeout(3000)

        await page.screenshot(path="page.png", full_page=True)

        await browser.close()


async def connect_jupiter():

    kp = Keypair()
    secret_64 = base64.b64encode(bytes(kp.to_bytes())).decode()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        page = await context.new_page()

        await page.goto(
            "https://jup.ag/limit?sell=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&buy=So11111111111111111111111111111111111111112",
            wait_until="domcontentloaded",
        )

        # Inject Solana SDK INLINE (CSP-safe)
        await page.add_script_tag(content=SOLANA_JS)

        # Inject Phantom
        await page.evaluate(get_solana_provider(secret_64))

        await page.wait_for_function("() => window.solana")

        pubkey = await page.evaluate(
            """() => {
          localStorage.setItem("userID", window.solana.publicKey.toBase58());
          localStorage.setItem("wallet-immersive-mode", "false");
          localStorage.setItem("walletName", '"Phantom"');                                     
          return window.solana.publicKey.toBase58();
        }""",
        )

        print("✅ Phantom connected:", pubkey)

        await page.wait_for_timeout(3000)

        await page.screenshot(path="page.png", full_page=True)
        await browser.close()


asyncio.run(connect_metamask())
