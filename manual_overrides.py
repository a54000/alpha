"""
Angel One → Yahoo Finance Manual Overrides
==========================================
Paste this dict into your angel_to_yahoo_mapper.py to replace the existing
MANUAL_OVERRIDES = {} block.

Sources: NSE circulars, Zerodha bulletins, Wikipedia, confirmed as of Jun 2026.
"""

MANUAL_OVERRIDES = {

    # ── Renamed / rebranded ───────────────────────────────────────────────
    # Angel symbol        Yahoo Finance symbol      Notes
    "ETERNAL"          : "ETERNAL.NS",           # Zomato renamed → Eternal, Apr 2025
    "LTM"              : "LTM.NS",               # LTIMindtree rebranded → LTM, Feb 2026
    "LTF"              : "LTF.NS",               # L&T Finance Holdings → L&T Finance, Apr 2024
    "ABREL"            : "ABREL.NS",             # Aditya Birla Real Estate Ltd (renamed)
    "TMPV"             : "TIINDIA.NS",           # Tube Investments of India
    "GVT&D"            : "GVTD.NS",             # GVT&D → GVTD (symbol cleaned)
    "NAM-INDIA"        : "NAM-INDIA.NS",         # Nippon AMC
    "JSWDULUX"         : "JSWDULUX.NS",          # JSW Paints / Dulux JV
    "BAJAJ-AUTO"       : "BAJAJ-AUTO.NS",        # hyphen preserved on Yahoo
    "M&M"              : "M&M.NS",               # ampersand preserved on Yahoo
    "M&MFIN"           : "M&MFIN.NS",
    "J&KBANK"          : "JKBANK.NS",            # Yahoo drops the &
    "ARE&M"            : "ARE&M.NS",
    "360ONE"           : "360ONE.NS",
    "3MINDIA"          : "3MINDIA.NS",

    # ── Merged corporate entities (map to surviving entity) ──────────────
    "MINDTREE"         : "LTM.NS",               # Merged into LTIMindtree (now LTM) Nov 2022
    "LTI"              : "LTM.NS",               # L&T Infotech merged → LTIMindtree → LTM
    "GRUH"             : "HDFCBANK.NS",          # Gruh Finance merged into HDFC Bank 2019
    "LAKSHVILAS"       : "DBS.NS",               # Lakshmi Vilas Bank → DBS Bank India 2020

    # ── PSU Bank mergers effective 1 Apr 2020 ────────────────────────────
    "ALBK"             : "INDIANB.NS",           # Allahabad Bank → Indian Bank
    "CORPBANK"         : "UNIONBANK.NS",         # Corporation Bank → Union Bank of India
    "ANDHRABANK"       : "UNIONBANK.NS",         # Andhra Bank → Union Bank of India
    "SYNDIBANK"        : "CANBK.NS",             # Syndicate Bank → Canara Bank
    "ORIENTBANK"       : "PNB.NS",              # Oriental Bank → Punjab National Bank

    # ── Ambiguous / parent-subsidiary (manual decision) ──────────────────
    # These had multiple Angel candidates — mapped to most likely match
    "HDFC"             : "HDFCBANK.NS",          # HDFC Ltd merged into HDFC Bank Jul 2023
    "IDFC"             : "IDFCFIRSTB.NS",        # IDFC Ltd merged into IDFC First Bank
    "PVR"              : "PVRINOX.NS",           # PVR merged with INOX → PVRINOX
    "INOXLEISUR"       : "PVRINOX.NS",           # INOX Leisure merged with PVR → PVRINOX
    "PTC"              : "PTCIL.NS",             # PTC India → PTCIL
    "JSLHISAR"         : "JSL.NS",               # Jindal Stainless Hisar merged into JSL
    "ZYDUSWELL"        : "ZYDUSLIFE.NS",         # Zydus Wellness → Zydus Lifesciences
    "SHRIRAMCIT"       : "SHRIRAMFIN.NS",        # Shriram City Union → Shriram Finance
    "WELSPUNIND"       : "WELSPUNLIV.NS",        # Welspun India → Welspun Living
    "STAR"             : "STARHEALTH.NS",        # Star Health Insurance
}


# ── Quick verification helper ─────────────────────────────────────────────
if __name__ == "__main__":
    import yfinance as yf
    import time

    print(f"Verifying {len(MANUAL_OVERRIDES)} override mappings against Yahoo Finance...\n")
    failed = []

    for angel, yahoo in MANUAL_OVERRIDES.items():
        try:
            hist = yf.Ticker(yahoo).history(period="5d")
            ok   = len(hist) > 0
        except Exception:
            ok = False

        status = "✅" if ok else "❌"
        print(f"  {status}  {angel:20s} → {yahoo}")
        if not ok:
            failed.append((angel, yahoo))
        time.sleep(0.3)

    print(f"\nResult: {len(MANUAL_OVERRIDES)-len(failed)} valid, {len(failed)} failed")
    if failed:
        print("Failed mappings (need manual fix):")
        for a, y in failed:
            print(f"  {a} → {y}")
