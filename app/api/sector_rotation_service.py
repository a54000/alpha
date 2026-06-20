"""Read-only sector rotation insight service."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

MIN_STOCKS_REQUIRED = 3
RS_SCORE_SCALE = 0.10
VOLUME_SCORE_SCALE = 0.25

INDUSTRY_TAXONOMY: dict[str, str] = {
    "HDFCBANK": "Private Banks",
    "ICICIBANK": "Private Banks",
    "KOTAKBANK": "Private Banks",
    "AXISBANK": "Private Banks",
    "INDUSINDBK": "Private Banks",
    "FEDERALBNK": "Private Banks",
    "IDFCFIRSTB": "Private Banks",
    "BANDHANBNK": "Private Banks",
    "RBLBANK": "Private Banks",
    "YESBANK": "Private Banks",
    "SBIN": "PSU Banks",
    "BANKBARODA": "PSU Banks",
    "PNB": "PSU Banks",
    "CANBK": "PSU Banks",
    "UNIONBANK": "PSU Banks",
    "INDIANB": "PSU Banks",
    "MAHABANK": "PSU Banks",
    "BAJFINANCE": "NBFCs",
    "BAJAJFINSV": "NBFCs",
    "SHRIRAMFIN": "NBFCs",
    "CHOLAFIN": "NBFCs",
    "MUTHOOTFIN": "NBFCs",
    "MANAPPURAM": "NBFCs",
    "M&MFIN": "NBFCs",
    "LTFH": "NBFCs",
    "POONAWALLA": "NBFCs",
    "AAVAS": "Housing Finance",
    "ABCAPITAL": "NBFCs",
    "AUBANK": "Private Banks",
    "BANKINDIA": "PSU Banks",
    "CANFINHOME": "Housing Finance",
    "CARERATING": "Credit Rating Agencies",
    "CENTRALBK": "PSU Banks",
    "CHOLAHLDNG": "NBFCs",
    "CREDITACC": "NBFCs",
    "CRISIL": "Credit Rating Agencies",
    "CUB": "Private Banks",
    "DCBBANK": "Private Banks",
    "EDELWEISS": "Capital Markets",
    "SUNDARMFIN": "NBFCs",
    "HDFCAMC": "Asset Management",
    "HUDCO": "Housing Finance",
    "ICRA": "Credit Rating Agencies",
    "IDBI": "PSU Banks",
    "IEX": "Power Exchange",
    "IFCI": "Development Finance",
    "INDOSTAR": "NBFCs",
    "IOB": "PSU Banks",
    "J&KBANK": "Private Banks",
    "JMFINANCIL": "Capital Markets",
    "KARURVYSYA": "Private Banks",
    "KTKBANK": "Private Banks",
    "LICHSGFIN": "Housing Finance",
    "MASFIN": "NBFCs",
    "MFSL": "Insurance",
    "PFC": "Government Finance",
    "PNBHOUSING": "Housing Finance",
    "RECLTD": "Government Finance",
    "REPCOHOME": "Housing Finance",
    "TATAINVEST": "Investment Companies",
    "UCOBANK": "PSU Banks",
    "BAJAJHLDNG": "Holdings",
    "BSE": "Capital Markets",
    "CDSL": "Capital Markets",
    "HDFC": "Housing Finance",
    "ICICIGI": "Insurance",
    "ICICIPRULI": "Insurance",
    "L&TFH": "NBFCs",
    "LICI": "Insurance",
    "NIACL": "Insurance",
    "STARHEALTH": "Insurance",
    "GICRE": "Insurance",
    "HDFCLIFE": "Insurance",
    "SBILIFE": "Insurance",
    "KFINTECH": "Capital Markets",
    "MCX": "Capital Markets",
    "ANGELONE": "Capital Markets",
    "MOTILALOFS": "Capital Markets",
    "IIFL": "Capital Markets",
    "TCS": "IT Services",
    "INFY": "IT Services",
    "WIPRO": "IT Services",
    "HCLTECH": "IT Services",
    "TECHM": "IT Services",
    "LTIM": "IT Services",
    "PERSISTENT": "IT Services",
    "COFORGE": "IT Services",
    "MPHASIS": "IT Services",
    "KPITTECH": "IT Services",
    "KPIT": "IT Services",
    "TATAELXSI": "IT Services",
    "HAPPSTMNDS": "IT Services",
    "OFSS": "IT Products",
    "MASTEK": "IT Products",
    "CYIENT": "IT Services",
    "ECLERX": "IT Services",
    "FSL": "IT Services",
    "INTELLECT": "IT Services",
    "JUSTDIAL": "Digital Services",
    "LTTS": "IT Services",
    "NAUKRI": "Digital Services",
    "SONATSOFTW": "IT Services",
    "ZENSARTECH": "IT Services",
    "M&M": "Passenger Vehicles",
    "MARUTI": "Passenger Vehicles",
    "TATAMOTORS": "Passenger Vehicles",
    "HYUNDAI": "Passenger Vehicles",
    "TIINDIA": "Passenger Vehicles",
    "BAJAJ-AUTO": "Two Wheelers",
    "HEROMOTOCO": "Two Wheelers",
    "EICHERMOT": "Two Wheelers",
    "TVSMOTOR": "Two Wheelers",
    "ASHOKLEY": "Commercial Vehicles",
    "MINDACORP": "Auto Ancillaries",
    "APOLLOTYRE": "Auto Ancillaries",
    "BALKRISIND": "Auto Ancillaries",
    "BOSCHLTD": "Auto Ancillaries",
    "CEATLTD": "Auto Ancillaries",
    "ENDURANCE": "Auto Ancillaries",
    "EXIDEIND": "Auto Ancillaries",
    "JAMNAAUTO": "Auto Ancillaries",
    "JKTYRE": "Auto Ancillaries",
    "MAHSCOOTER": "Auto Ancillaries",
    "MRF": "Auto Ancillaries",
    "ESCORTS": "Farm Equipment",
    "SUNPHARMA": "Pharma",
    "DRREDDY": "Pharma",
    "CIPLA": "Pharma",
    "DIVISLAB": "Pharma",
    "TORNTPHARM": "Pharma",
    "ALKEM": "Pharma",
    "AUROPHARMA": "Pharma",
    "LUPIN": "Pharma",
    "GLENMARK": "Pharma",
    "IPCALAB": "Pharma",
    "BIOCON": "Biotech",
    "AJPHARM": "Pharma",
    "AJANTPHARM": "Pharma",
    "APLLTD": "Pharma",
    "ASTRAZEN": "Pharma",
    "BLISSGVS": "Pharma",
    "CAPLIPOINT": "Pharma",
    "DCAL": "Pharma",
    "ERIS": "Pharma",
    "FDC": "Pharma",
    "GLAXO": "Pharma",
    "GRANULES": "Pharma",
    "INDOCO": "Pharma",
    "JBCHEPHARM": "Pharma",
    "LAURUSLABS": "Pharma",
    "NATCOPHARM": "Pharma",
    "PFIZER": "Pharma",
    "PGHL": "Pharma",
    "SANOFI": "Pharma",
    "SHILPAMED": "Pharma",
    "SYNGENE": "Biotech",
    "WOCKPHARMA": "Pharma",
    "ANTINNH": "Healthcare Services",
    "ASTERDM": "Hospitals",
    "METROPOLIS": "Diagnostics",
    "LALPATHLAB": "Diagnostics",
    "THYROCARE": "Diagnostics",
    "KIMS": "Hospitals",
    "MAXHEALTH": "Hospitals",
    "FORTIS": "Hospitals",
    "APOLLOHOSP": "Hospitals",
    "NH": "Hospitals",
    "ACC": "Cement",
    "AMBUJACEM": "Cement",
    "BIRLACORPN": "Cement",
    "GRASIM": "Cement",
    "HEIDELBERG": "Cement",
    "INDIACEM": "Cement",
    "JKCEMENT": "Cement",
    "JKLAKSHMI": "Cement",
    "ORIENTCEM": "Cement",
    "PRSMJOHNSN": "Cement",
    "RAMCOCEM": "Cement",
    "SHREECEM": "Cement",
    "ULTRACEMCO": "Cement",
    "ATUL": "Specialty Chemicals",
    "BASF": "Specialty Chemicals",
    "DEEPAKFERT": "Agrochemicals",
    "DEEPAKNTR": "Specialty Chemicals",
    "FINEORG": "Specialty Chemicals",
    "GALAXYSURF": "Specialty Chemicals",
    "GHCL": "Industrial Chemicals",
    "GNFC": "Industrial Chemicals",
    "GUJALKALI": "Industrial Chemicals",
    "HSCL": "Specialty Chemicals",
    "LINDEINDIA": "Industrial Gases",
    "NAVINFLUOR": "Specialty Chemicals",
    "PIDILITIND": "Adhesives",
    "RAIN": "Cement",
    "SOLARINDS": "Industrial Explosives",
    "TATACHEM": "Industrial Chemicals",
    "ASHOKA": "Infrastructure",
    "BRIGADE": "Residential Real Estate",
    "CERA": "Building Materials",
    "DBL": "Infrastructure",
    "DLF": "Residential Real Estate",
    "ENGINERSIN": "Engineering & Construction",
    "GODREJPROP": "Residential Real Estate",
    "IRB": "Infrastructure",
    "IRCON": "Engineering & Construction",
    "KAJARIACER": "Building Materials",
    "KEC": "Engineering & Construction",
    "KNRCON": "Infrastructure",
    "KOLTEPATIL": "Residential Real Estate",
    "LT": "Engineering & Construction",
    "NBCC": "Engineering & Construction",
    "NCC": "Engineering & Construction",
    "OBEROIRLTY": "Residential Real Estate",
    "OMAXE": "Residential Real Estate",
    "PHOENIXLTD": "Commercial Real Estate",
    "PNCINFRA": "Infrastructure",
    "PRESTIGE": "Residential Real Estate",
    "RITES": "Engineering & Construction",
    "SADBHAV": "Infrastructure",
    "SOBHA": "Residential Real Estate",
    "ABFRL": "Apparel Retail",
    "ADVENZYMES": "Agri & Food Ingredients",
    "ASIANPAINT": "Paints",
    "AVANTIFEED": "Aquaculture",
    "BAJAJCON": "Personal Care",
    "BAJAJELEC": "Consumer Durables",
    "BALRAMCHIN": "Sugar",
    "BATAINDIA": "Footwear",
    "BBTC": "Tea & Beverages",
    "BERGEPAINT": "Paints",
    "BLUESTARCO": "Consumer Durables",
    "BRITANNIA": "Food & Beverages",
    "CCL": "Tea & Coffee",
    "CENTURYPLY": "Building Materials",
    "COLPAL": "Personal Care",
    "CROMPTON": "Consumer Durables",
    "DABUR": "Personal Care",
    "DCMSHRIRAM": "Sugar",
    "DIXON": "Consumer Electronics",
    "DMART": "Retail",
    "EMAMILTD": "Personal Care",
    "GILLETTE": "Personal Care",
    "GODFRYPHLP": "Food & Beverages",
    "GODREJAGRO": "Agri & Food Ingredients",
    "GODREJCP": "Personal Care",
    "GODREJIND": "Household Products",
    "HATSUN": "Dairy",
    "HAVELLS": "Consumer Durables",
    "HERITGFOOD": "Dairy",
    "HINDUNILVR": "Personal Care",
    "IFBIND": "Consumer Durables",
    "ITC": "FMCG Diversified",
    "JUBLFOOD": "Restaurants",
    "JYOTHYLAB": "Personal Care",
    "KANSAINER": "Paints",
    "KRBL": "Agri & Food Ingredients",
    "KSCL": "Agri & Food Ingredients",
    "MARICO": "Personal Care",
    "ORIENTELEC": "Consumer Durables",
    "PARAGMILK": "Dairy",
    "PCJEWELLER": "Jewellery",
    "PGHH": "Personal Care",
    "RADICO": "Alcoholic Beverages",
    "RELAXO": "Footwear",
    "RENUKA": "Sugar",
    "SFL": "Food Processing",
    "SHK": "Agri & Food Ingredients",
    "SHOPERSTOP": "Retail",
    "TITAN": "Jewellery",
    "TRENT": "Retail",
    "UBL": "Alcoholic Beverages",
    "VBL": "Beverages",
    "VOLTAS": "Consumer Durables",
    "WHIRLPOOL": "Consumer Durables",
    "ADANIGREEN": "Renewable Energy",
    "ADANIPOWER": "Power Generation",
    "BPCL": "Oil & Gas",
    "CASTROLIND": "Lubricants",
    "CESC": "Power Generation",
    "CHENNPETRO": "Oil & Gas",
    "GAIL": "Gas Distribution",
    "GUJGASLTD": "Gas Distribution",
    "GULFOILLUB": "Lubricants",
    "HINDPETRO": "Oil & Gas",
    "IGL": "Gas Distribution",
    "IOC": "Oil & Gas",
    "JSWENERGY": "Power Generation",
    "MGL": "Gas Distribution",
    "MRPL": "Oil & Gas",
    "NHPC": "Power Generation",
    "NLCINDIA": "Power Generation",
    "NTPC": "Power Generation",
    "OIL": "Oil & Gas",
    "ONGC": "Oil & Gas",
    "PETRONET": "Gas Infrastructure",
    "POWERGRID": "Power Transmission",
    "PTC": "Power Trading",
    "RELIANCE": "Oil & Gas",
    "RPOWER": "Power Generation",
    "SJVN": "Power Generation",
    "TATAPOWER": "Power Generation",
    "TORNTPOWER": "Power Generation",
    "CHAMBLFERT": "Fertilisers",
    "COROMANDEL": "Fertilisers",
    "EIDPARRY": "Agri Inputs",
    "GSFC": "Fertilisers",
    "NFL": "Fertilisers",
    "PIIND": "Agrochemicals",
    "RALLIS": "Agrochemicals",
    "RCF": "Fertilisers",
    "SHARDACROP": "Agrochemicals",
    "UPL": "Agrochemicals",
    "HATHWAY": "Broadcast Media",
    "DBCORP": "Print Media",
    "JAGRAN": "Print Media",
    "NETWORK18": "Broadcast Media",
    "SUNTV": "Broadcast Media",
    "ZEEL": "Broadcast Media",
    "APLAPOLLO": "Steel Products",
    "COALINDIA": "Mining",
    "GMDCLTD": "Mining",
    "HINDALCO": "Aluminium",
    "HINDCOPPER": "Copper",
    "HINDZINC": "Zinc",
    "JINDALSAW": "Steel Pipes",
    "JINDALSTEL": "Steel",
    "JSL": "Stainless Steel",
    "JSWSTEEL": "Steel",
    "KIOCL": "Iron Ore",
    "MAHSEAMLES": "Steel Pipes",
    "MOIL": "Mining",
    "NATIONALUM": "Aluminium",
    "NMDC": "Mining",
    "SAIL": "Steel",
    "TATASTEEL": "Steel",
    "VEDL": "Diversified Metals",
    "WELCORP": "Steel Pipes",
    "JKPAPER": "Paper",
    "3MINDIA": "Industrial Services",
    "ADANIPORTS": "Ports & Logistics",
    "ALLCARGO": "Logistics",
    "BALMLAWRIE": "Industrial Services",
    "BLUEDART": "Logistics",
    "CONCOR": "Logistics",
    "DELTACORP": "Gaming & Leisure",
    "EIHOTEL": "Hotels",
    "GESHIP": "Shipping",
    "GPPL": "Ports & Logistics",
    "INDHOTEL": "Hotels",
    "INDIGO": "Airlines",
    "ITDC": "Hotels",
    "LEMONTREE": "Hotels",
    "MAHLOG": "Logistics",
    "MHRIL": "Hotels",
    "MMTC": "Trading",
    "NESCO": "Commercial Real Estate",
    "QUESS": "Staffing Services",
    "REDINGTON": "Technology Distribution",
    "SCI": "Shipping",
    "SIS": "Security Services",
    "BHARTIARTL": "Telecom Services",
    "HFCL": "Telecom Equipment",
    "IDEA": "Telecom Services",
    "ITI": "Telecom Equipment",
    "ABB": "Electrical Equipment",
    "AIAENG": "Industrial Machinery",
    "ASTRAL": "Pipes & Fittings",
    "BDL": "Aerospace & Defence",
    "BEL": "Aerospace & Defence",
    "BEML": "Aerospace & Defence",
    "BHARATFORG": "Auto Ancillaries",
    "BHEL": "Heavy Engineering",
    "CARBORUNIV": "Industrial Ceramics",
    "CGPOWER": "Electrical Equipment",
    "COCHINSHIP": "Shipbuilding",
    "CUMMINSIND": "Industrial Machinery",
    "ELGIEQUIP": "Industrial Machinery",
    "FINCABLES": "Cables",
    "FINPIPE": "Pipes & Fittings",
    "GRAPHITE": "Industrial Materials",
    "GREAVESCOT": "Industrial Machinery",
    "GRINDWELL": "Industrial Machinery",
    "HAL": "Aerospace & Defence",
    "HEG": "Industrial Materials",
    "HONAUT": "Electrical Equipment",
    "INOXWIND": "Renewable Energy",
    "JAICORPLTD": "Industrial Construction",
    "JISLJALEQS": "Pipes & Fittings",
    "KEI": "Cables",
    "KIRLOSENG": "Industrial Machinery",
    "NILKAMAL": "Industrial Products",
    "PRAJIND": "Industrial Machinery",
    "RKFORGE": "Auto Ancillaries",
    "SCHAEFFLER": "Industrial Machinery",
    "SIEMENS": "Electrical Equipment",
    "SKFINDIA": "Industrial Machinery",
    "SUPREMEIND": "Plastics",
    "SUZLON": "Renewable Energy",
    "THERMAX": "Industrial Machinery",
    "TIMKEN": "Industrial Machinery",
    "TRITURBINE": "Industrial Machinery",
    "BOMDYEING": "Textiles",
    "HIMATSEIDE": "Textiles",
    "KPRMILL": "Textiles",
    "LUXIND": "Textiles",
    "PAGEIND": "Textiles",
    "RAYMOND": "Textiles",
    "RUPA": "Textiles",
    "SRF": "Technical Textiles",
    "TRIDENT": "Textiles",
    "VTL": "Textiles",
    "IRCTC": "Travel & Tourism",
    "EASEMYTRIP": "Travel & Tourism",
    "IXIGO": "Travel & Tourism",
    "INTERGLOBE": "Aviation",
    "SPICEJET": "Aviation",
    "TV18BRDCST": "Broadcast Media",
    "PVRINOX": "Film Exhibition",
    "INOXGREEN": "Film Exhibition",
    "TIPS": "Music & Content",
    "SAREGAMA": "Music & Content",
}



class SectorRotationError(RuntimeError):
    """Raised when sector rotation insights cannot be generated."""


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


class SectorRotationService:
    """Compute sector rotation views from existing pilot market data."""

    def __init__(self, angel_database_url: str | None = None, pilot_schema: str = "pilot_phase2a") -> None:
        research_url = os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url)
        if not self.angel_database_url:
            raise SectorRotationError("ANGEL_DATABASE_URL is required for sector rotation insights.")
        self.engine = make_engine(self.angel_database_url)
        self.pilot_schema = pilot_schema
        self.nifty500_csv = Path(__file__).resolve().parents[2] / "data" / "ind_nifty500list.csv"
        self._validate_taxonomy_configuration()

    def insights(self, as_of: date | None = None) -> dict[str, object]:
        latest = as_of or self._latest_date()
        if latest is None:
            return {"as_of": None, "sectors": [], "summary": {}}
        frame = self._load_sector_frame(latest)
        nifty = self._load_nifty50_frame(latest)
        if frame.empty:
            raise SectorRotationError("Sector data is required for sector rotation insights.")
        if nifty.empty:
            raise SectorRotationError("NIFTY50 benchmark data is required for sector rotation insights.")
        sector_daily = self._sector_daily(frame)
        rows = self._compute_sector_rrg(sector_daily, nifty, latest)
        if not rows:
            raise SectorRotationError("Insufficient sector or benchmark history for RRG calculation.")
        rows.sort(key=lambda row: (row["rs_ratio"] or 0.0, row["rs_momentum"] or 0.0), reverse=True)
        diagnostics = self._diagnostics(rows)
        return {
            "as_of": latest.isoformat(),
            "benchmark": "NIFTY50",
            "windows": {"rrg_smooth": 10, "rrg_ratio_mean": 52, "tail": 4},
            "summary": self._summary(rows),
            "diagnostics": diagnostics,
            "sectors": rows,
        }

    def industry_confirmation(self, sector: str | None = None, as_of: date | None = None) -> dict[str, object]:
        latest = as_of or self._latest_date()
        if latest is None:
            return {"as_of": None, "industries": [], "summary": {}}
        sector_frame = self._load_sector_frame(latest)
        nifty = self._load_nifty50_frame(latest)
        if sector_frame.empty:
            raise SectorRotationError("Industry confirmation requires sector price history.")
        if nifty.empty:
            raise SectorRotationError("Industry confirmation requires NIFTY50 benchmark history.")
        mapped = self._attach_industry_map(sector_frame)
        if sector and sector.strip():
            mapped = mapped[mapped["sector"].astype(str).str.upper() == sector.strip().upper()]
        if mapped.empty:
            raise SectorRotationError("No mapped industries available for the requested sector.")
        industries = self._industry_confirmation_rows(mapped, nifty, latest)
        return {
            "as_of": latest.isoformat(),
            "sector": sector,
            "summary": self._industry_summary(industries),
            "industries": industries,
        }

    def _latest_date(self) -> date | None:
        with self.engine.connect() as connection:
            return connection.execute(text(f"SELECT MAX(date) FROM {self.pilot_schema}.features_daily")).scalar_one_or_none()

    def _load_sector_frame(self, latest: date) -> pd.DataFrame:
        query = text(
            f"""
            SELECT f.symbol, f.date, f.sector, b.close, b.volume
            FROM {self.pilot_schema}.features_daily f
            JOIN {self.pilot_schema}.daily_bars_clean b
              ON b.symbol = f.symbol
             AND b.date = f.date
            WHERE f.date BETWEEN :latest - INTERVAL '140 days' AND :latest
              AND f.sector IS NOT NULL
              AND b.close IS NOT NULL
            ORDER BY f.sector, f.symbol, f.date
            """
        )
        frame = pd.read_sql_query(query, self.engine, params={"latest": latest})
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
        frame["turnover"] = frame["close"] * frame["volume"]
        return frame.dropna(subset=["close"])

    def _attach_industry_map(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.nifty500_csv.exists():
            raise SectorRotationError("Nifty 500 universe file is required for industry confirmation.")
        mapping = pd.read_csv(self.nifty500_csv)
        mapping["symbol"] = mapping["Symbol"].astype(str).str.strip().str.upper()
        mapping["sector_master"] = mapping["Industry"].fillna("").astype(str)
        mapping["industry_csv"] = mapping["Industry"].fillna("").astype(str)
        mapping["industry_taxonomy"] = mapping["symbol"].map(INDUSTRY_TAXONOMY).fillna("")
        item = frame.copy()
        item["symbol"] = item["symbol"].astype(str).str.upper()
        merged = item.merge(mapping[["symbol", "sector_master", "industry_csv", "industry_taxonomy"]], on="symbol", how="left")
        merged["sector_norm"] = merged["sector_master"].where(merged["sector_master"].fillna("") != "", merged["sector"]).fillna("").astype(str)
        merged["industry_norm"] = merged["industry_taxonomy"].where(
            merged["industry_taxonomy"].fillna("") != "",
            merged["industry_csv"],
        ).fillna("").astype(str)
        merged["taxonomy_tier"] = np.where(
            merged["industry_taxonomy"].fillna("") != "",
            "hardcoded",
            np.where(merged["industry_csv"].fillna("") != "", "nse_csv", "missing"),
        )
        return merged

    def _industry_confirmation_rows(self, mapped: pd.DataFrame, nifty: pd.DataFrame, latest: date) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        coverage_gaps: list[str] = []
        for (sector_name, industry), group in mapped.groupby(["sector_norm", "industry_norm"], dropna=False):
            industry_name = str(industry).strip() or "Unclassified"
            sector_name = str(sector_name).strip() or "Unknown"
            if not industry_name or industry_name == "Unclassified":
                continue
            tier_series = group["taxonomy_tier"] if "taxonomy_tier" in group.columns else pd.Series(dtype=str)
            if industry_name.upper() == sector_name.upper() and not tier_series.eq("hardcoded").any():
                coverage_gaps.extend(sorted(set(group["symbol"].astype(str))))
                continue
            symbols = sorted(set(group["symbol"].astype(str)))
            if not symbols:
                continue
            sector_group = mapped[mapped["sector_norm"] == sector_name]
            sector_prices = self._group_index_series(sector_group, "sector_index", "sector_norm")
            industry_prices = self._group_index_series(group, "industry_index", "industry_norm")
            if industry_prices.empty or sector_prices.empty:
                continue
            score_row = self._score_industry(group, sector_group, latest)
            if score_row is not None:
                score_row["sector"] = sector_name
                score_row["industry"] = industry_name
                score_row["stock_count"] = len(symbols)
                score_row["reliable"] = len(symbols) >= MIN_STOCKS_REQUIRED
                score_row["taxonomy_tier"] = str(group["taxonomy_tier"].mode().iloc[0]) if "taxonomy_tier" in group.columns and not group["taxonomy_tier"].empty else "missing"
                if len(symbols) < MIN_STOCKS_REQUIRED:
                    score_row["status"] = "Insufficient"
                    score_row["composite"] = 0.0
                    score_row["breadth_pct"] = 0.0
                    score_row["relative_strength"] = 0.0
                    score_row["volume_trend"] = 0.0
                    score_row["structure_pct"] = 0.0
                    score_row["coverage_note"] = f"Only {len(symbols)} stock(s) in this industry. Minimum {MIN_STOCKS_REQUIRED} required for reliable breadth signal."
                rows.append(score_row)
        if coverage_gaps:
            rows.append(
                {
                    "as_of": latest.isoformat(),
                    "breadth_pct": 0.0,
                    "relative_strength": 0.0,
                    "volume_trend": 0.0,
                    "structure_pct": 0.0,
                    "composite": 0.0,
                    "status": "Coverage Gap",
                    "reliable": False,
                    "sector": str(mapped["sector_norm"].dropna().iloc[0]) if not mapped.empty else "Unknown",
                    "industry": "__UNMAPPED__",
                    "tickers": sorted(set(coverage_gaps)),
                    "stock_count": len(coverage_gaps),
                    "taxonomy_tier": "sector_fallback",
                    "coverage_note": (
                        f"{len(coverage_gaps)} symbol(s) have no industry mapping beyond the sector name itself. "
                        f"Add these to INDUSTRY_TAXONOMY to improve coverage: "
                        f"{', '.join(sorted(set(coverage_gaps))[:10])}"
                        f"{'...' if len(set(coverage_gaps)) > 10 else ''}"
                    ),
                }
            )
        reliable = [r for r in rows if r.get("reliable")]
        insufficient = [r for r in rows if not r.get("reliable") and r.get("status") == "Insufficient"]
        coverage_only = [r for r in rows if r.get("status") == "Coverage Gap"]
        reliable.sort(key=lambda x: float(x.get("composite") or 0.0), reverse=True)
        insufficient.sort(key=lambda x: str(x.get("industry") or ""))
        return reliable + insufficient + coverage_only

    @staticmethod
    def _group_index_series(group: pd.DataFrame, index_column: str, group_column: str) -> pd.DataFrame:
        if group.empty:
            return pd.DataFrame()
        item = group.copy()
        item["close"] = pd.to_numeric(item["close"], errors="coerce")
        item["volume"] = pd.to_numeric(item["volume"], errors="coerce").fillna(0.0)
        daily = (
            item.sort_values([group_column, "symbol", "date"])
            .groupby([group_column, "date"], as_index=False)
            .agg(close=("close", "mean"), volume=("volume", "sum"))
            .sort_values("date")
        )
        daily[index_column] = (1.0 + daily["close"].pct_change().fillna(0.0)).cumprod()
        return daily[["date", index_column, "volume"]]

    def _score_industry(self, industry_group: pd.DataFrame, sector_group: pd.DataFrame, latest: date) -> dict[str, object] | None:
        if industry_group.empty or sector_group.empty:
            return None
        industry_scores = self._member_scores(industry_group)
        sector_scores = self._member_scores(sector_group)
        if not industry_scores or not sector_scores:
            return None
        breadth_pct = float(np.mean([row["above_20ema"] for row in industry_scores]) * 100)
        structure_pct = float(np.mean([row["near_high"] for row in industry_scores]) * 100)
        industry_return_20 = float(np.mean([row["return_20"] for row in industry_scores if row["return_20"] is not None]))
        sector_return_20 = float(np.mean([row["return_20"] for row in sector_scores if row["return_20"] is not None]))
        rs_vs_sector = industry_return_20 - sector_return_20
        volume_trend = float(np.mean([row["volume_trend"] for row in industry_scores if row["volume_trend"] is not None]))
        rs_score = self._rs_score(rs_vs_sector)
        volume_score = self._volume_score(volume_trend)
        composite = breadth_pct * 0.35 + rs_score * 0.30 + volume_score * 0.15 + structure_pct * 0.20
        status = "Strong" if composite >= 70 else "Moderate" if composite >= 50 else "Weak" if composite >= 30 else "Avoid"
        return {
            "as_of": latest.isoformat(),
            "breadth_pct": float(round(breadth_pct, 1)),
            "relative_strength": float(round(rs_score, 1)),
            "volume_trend": float(round(volume_trend, 2)) if volume_trend is not None else None,
            "structure_pct": float(round(structure_pct, 1)),
            "composite": float(round(composite, 1)),
            "status": status,
            "reliable": True,
        }

    @staticmethod
    def _rs_score(rs_vs_sector: float | None) -> float:
        """Map 20-day industry-vs-sector return differential onto 0-100."""
        if rs_vs_sector is None:
            return 0.0
        score = 50.0 + (rs_vs_sector / RS_SCORE_SCALE) * 50.0
        return float(np.clip(score, 0.0, 100.0))

    @staticmethod
    def _volume_score(volume_trend: float | None) -> float:
        """Map 10d/30d volume ratio onto 0-100 centered at 1.0 -> 50."""
        if volume_trend is None:
            return 0.0
        score = 50.0 + ((volume_trend - 1.0) / VOLUME_SCORE_SCALE) * 50.0
        return float(np.clip(score, 0.0, 100.0))

    @staticmethod
    def _member_scores(group: pd.DataFrame) -> list[dict[str, object]]:
        scores: list[dict[str, object]] = []
        for symbol, member in group.groupby("symbol"):
            member = member.sort_values("date")
            close = pd.to_numeric(member["close"], errors="coerce").dropna()
            volume = pd.to_numeric(member["volume"], errors="coerce").fillna(0.0)
            if len(close) < 21:
                continue
            ema20 = close.ewm(span=20, adjust=False).mean()
            above_20ema = bool(close.iloc[-1] > ema20.iloc[-1])
            high_20 = close.iloc[-21:-1].max()
            near_high = bool(high_20 > 0 and close.iloc[-1] >= high_20 * 0.995)
            return_20 = float(close.iloc[-1] / close.iloc[-21] - 1)
            recent_vol = float(volume.iloc[-10:].mean()) if len(volume) >= 10 else None
            prior_vol = float(volume.iloc[-31:-11].mean()) if len(volume) >= 31 else None
            volume_trend = (recent_vol / prior_vol) if prior_vol and prior_vol > 0 else None
            scores.append(
                {
                    "symbol": symbol,
                    "above_20ema": above_20ema,
                    "near_high": near_high,
                    "return_20": return_20,
                    "volume_trend": volume_trend,
                }
            )
        return scores

    @staticmethod
    def _validate_taxonomy_configuration() -> None:
        """Fail fast if obvious core taxonomy anchors are missing."""
        required = {
            "HDFCBANK",
            "ICICIBANK",
            "SBIN",
            "TCS",
            "INFY",
            "SUNPHARMA",
            "MARUTI",
            "RELIANCE",
            "ACC",
            "BHARTIARTL",
        }
        missing = sorted(symbol for symbol in required if symbol not in INDUSTRY_TAXONOMY)
        if missing:
            raise SectorRotationError(f"Taxonomy configuration is incomplete: {', '.join(missing)}")

    def _load_nifty50_frame(self, latest: date) -> pd.DataFrame:
        query = text(
            """
            SELECT datetime::date AS date, close
            FROM ohlcv_15min
            WHERE symbol = 'NIFTY50'
              AND datetime::date BETWEEN :latest - INTERVAL '140 days' AND :latest
              AND datetime::time <= '15:15:00'
            ORDER BY datetime
            """
        )
        frame = pd.read_sql_query(query, self.engine, params={"latest": latest})
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        return frame.dropna().groupby("date", as_index=False).tail(1)[["date", "close"]]

    @staticmethod
    def _sector_daily(frame: pd.DataFrame) -> pd.DataFrame:
        item = frame.sort_values(["sector", "symbol", "date"]).copy()
        item["stock_return_1d"] = item.groupby("symbol")["close"].pct_change()
        daily = (
            item.groupby(["sector", "date"], as_index=False)
            .agg(
                sector_return_1d=("stock_return_1d", "mean"),
                turnover=("turnover", "sum"),
                bullish_pct=("stock_return_1d", lambda values: float((values > 0).mean()) if len(values) else None),
                constituents=("symbol", "nunique"),
            )
            .sort_values(["sector", "date"])
        )
        daily["sector_index"] = (1.0 + daily["sector_return_1d"].fillna(0.0)).groupby(daily["sector"]).cumprod()
        daily["turnover_avg_21d"] = daily.groupby("sector")["turnover"].transform(lambda values: values.rolling(21, min_periods=5).mean())
        daily["turnover_ratio"] = daily["turnover"] / daily["turnover_avg_21d"].replace(0, pd.NA)
        daily["bullish_pct_5d"] = daily.groupby("sector")["bullish_pct"].transform(lambda values: values.rolling(5, min_periods=3).mean())
        daily["bullish_pct_21d"] = daily.groupby("sector")["bullish_pct"].transform(lambda values: values.rolling(21, min_periods=8).mean())
        return daily

    def _compute_sector_rrg(
        self,
        sector_daily: pd.DataFrame,
        nifty: pd.DataFrame,
        latest: date,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        benchmark_prices = nifty.sort_values("date").set_index("date")["close"].astype(float)
        for sector, group in sector_daily.groupby("sector"):
            group = group.sort_values("date")
            if group.empty:
                continue
            sector_prices = group.set_index("date")["sector_index"].astype(float)
            rrg = self._compute_sector_rrg_series(sector_prices, benchmark_prices)
            if not rrg:
                continue
            latest_point = rrg[-1]
            quadrant = self._quadrant(latest_point["rs_ratio"], latest_point["rs_momentum"])
            direction = self._direction(quadrant, latest_point["tail_direction"])
            priority = self._priority(quadrant, latest_point["tail_direction"])
            action = self._action(quadrant, latest_point["tail_direction"])
            rows.append(
                {
                    "sector": str(sector),
                    "as_of": latest.isoformat(),
                    "constituents": int(group.iloc[-1].get("constituents") or 0),
                    "sector_return_1w": None,
                    "sector_return_1m": None,
                    "sector_return_3m": None,
                    "relative_strength_1w": None,
                    "relative_strength_1m": None,
                    "relative_strength_3m": None,
                    "rs_ratio": latest_point["rs_ratio"],
                    "rs_momentum": latest_point["rs_momentum"],
                    "quadrant": quadrant,
                    "tail_direction": latest_point["tail_direction"],
                    "layer2_action": action,
                    "layer2_bias": self._bias(quadrant),
                    "layer2_priority": priority,
                    "layer2_interpretation": self._interpretation(quadrant, latest_point["tail_direction"]),
                    "long_eligible": direction == "LONG",
                    "short_eligible": direction == "SHORT",
                    "classification_confidence": self._confidence(latest_point["rs_ratio"]),
                    "tail": latest_point["tail_history"],
                    "turnover_ratio": self._float_or_none(group.iloc[-1].get("turnover_ratio")),
                    "bullish_pct_today": self._float_or_none(group.iloc[-1].get("bullish_pct")),
                    "bullish_pct_1w": self._float_or_none(group.iloc[-1].get("bullish_pct_5d")),
                    "bullish_pct_1m": self._float_or_none(group.iloc[-1].get("bullish_pct_21d")),
                    "rotation_score": latest_point["rs_ratio"],
                    "interpretation": self._interpretation(quadrant, latest_point["tail_direction"]),
                }
            )
        return rows

    @staticmethod
    def _compute_sector_rrg_series(
        sector_prices: pd.Series,
        benchmark_prices: pd.Series,
        smooth_window: int = 10,
        ratio_window: int = 52,
        tail_length: int = 4,
    ) -> list[dict[str, object]]:
        frame = pd.concat([sector_prices.rename("sector"), benchmark_prices.rename("benchmark")], axis=1).dropna()
        if len(frame) < ratio_window:
            return []
        rs_raw = frame["sector"] / frame["benchmark"]
        rs_smooth = rs_raw.ewm(span=smooth_window, adjust=False).mean()
        rs_ratio = (rs_smooth / rs_smooth.rolling(ratio_window).mean()) * 100
        rs_momentum = rs_ratio.pct_change(periods=1) * 100 + 100
        frame["rs_ratio"] = rs_ratio
        frame["rs_momentum"] = rs_momentum
        tail = frame.dropna(subset=["rs_ratio", "rs_momentum"]).tail(tail_length)
        if tail.empty:
            return []
        values = [
            {
                "date": index.isoformat() if hasattr(index, "isoformat") else str(index),
                "rs_ratio": float(row.rs_ratio),
                "rs_momentum": float(row.rs_momentum),
            }
            for index, row in tail.iterrows()
        ]
        latest = values[-1]
        latest["tail_history"] = [
            {
                "date": item["date"],
                "rs_ratio": item["rs_ratio"],
                "rs_momentum": item["rs_momentum"],
            }
            for item in values
        ]
        latest["tail_direction"] = SectorRotationService._tail_direction_series(values)
        return [latest]

    @staticmethod
    def _quadrant(rs_ratio: float | None, rs_momentum: float | None) -> str:
        if rs_ratio is None or rs_momentum is None:
            return "unknown"
        if rs_ratio >= 100 and rs_momentum >= 100:
            return "leading"
        if rs_ratio >= 100 and rs_momentum < 100:
            return "weakening"
        if rs_ratio < 100 and rs_momentum < 100:
            return "lagging"
        return "improving"

    @staticmethod
    def _tail_direction_series(tail: list[dict[str, object]]) -> str:
        if len(tail) < 2:
            return "unknown"
        first = SectorRotationService._float_or_none(tail[0].get("rs_ratio"))
        last = SectorRotationService._float_or_none(tail[-1].get("rs_ratio"))
        if first is None or last is None:
            return "unknown"
        if abs(last - first) < 0.10:
            return "flat"
        return "right" if last > first else "left"

    @staticmethod
    def _bias(quadrant: str) -> str:
        return {
            "leading": "long",
            "improving": "watch_long",
            "weakening": "watch_turn",
            "lagging": "short",
        }.get(quadrant, "wait")

    @staticmethod
    def _direction(quadrant: str, tail_direction: str) -> str:
        if quadrant == "leading" and tail_direction == "right":
            return "LONG"
        if quadrant == "improving" and tail_direction == "right":
            return "WATCH_LONG"
        if quadrant == "weakening" and tail_direction == "left":
            return "WATCH_SHORT"
        if quadrant == "lagging" and tail_direction == "left":
            return "SHORT"
        return "HOLD"

    @staticmethod
    def _priority(quadrant: str, tail_direction: str) -> int:
        if quadrant == "leading" and tail_direction == "right":
            return 1
        if quadrant == "improving" and tail_direction == "right":
            return 2
        if quadrant == "weakening" and tail_direction == "left":
            return 3
        if quadrant == "lagging" and tail_direction == "left":
            return 4
        return 5

    @staticmethod
    def _action(quadrant: str, tail_direction: str) -> str:
        return {
            ("leading", "right"): "fresh_long_candidate",
            ("improving", "right"): "early_long_watch",
            ("weakening", "left"): "watch_short",
            ("lagging", "left"): "fresh_short_candidate",
        }.get((quadrant, tail_direction), "wait")

    @staticmethod
    def _interpretation(quadrant: str, tail_direction: str) -> str:
        if quadrant == "leading" and tail_direction == "right":
            return "Strong long candidate: sector is outperforming and still accelerating."
        if quadrant == "improving" and tail_direction == "right":
            return "Early long watch: relative strength is improving; wait for confirmation."
        if quadrant == "weakening" and tail_direction == "left":
            return "Watch short: sector is weakening and tail confirms deterioration."
        if quadrant == "lagging" and tail_direction == "left":
            return "Strong short candidate: sector is underperforming and deteriorating."
        return "No confirmed Layer 2 action; wait for clearer quadrant and tail alignment."

    @staticmethod
    def _confidence(rs_ratio: float | None) -> str:
        if rs_ratio is None:
            return "insufficient"
        distance = abs(rs_ratio - 100.0)
        if distance < 1.5:
            return "borderline"
        if distance < 3.0:
            return "moderate"
        return "clear"

    @staticmethod
    def _diagnostics(rows: list[dict[str, object]]) -> dict[str, object]:
        ratios = [float(row["rs_ratio"]) for row in rows if row.get("rs_ratio") is not None]
        momentums = [float(row["rs_momentum"]) for row in rows if row.get("rs_momentum") is not None]
        borderline = [row["sector"] for row in rows if row.get("classification_confidence") == "borderline"]
        ratio_spread = max(ratios) - min(ratios) if ratios else None
        momentum_spread = max(momentums) - min(momentums) if momentums else None
        return {
            "rs_ratio_min": min(ratios) if ratios else None,
            "rs_ratio_max": max(ratios) if ratios else None,
            "rs_ratio_spread": ratio_spread,
            "rs_momentum_min": min(momentums) if momentums else None,
            "rs_momentum_max": max(momentums) if momentums else None,
            "rs_momentum_spread": momentum_spread,
            "borderline_sectors": borderline,
            "caution": (
                "RRG spread is tight; sectors near 100 should be read by tail direction, not only quadrant."
                if ratio_spread is not None and ratio_spread < 4.0
                else None
            ),
        }

    @staticmethod
    def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
        leading = [row["sector"] for row in rows if row["quadrant"] == "leading"]
        improving = [row["sector"] for row in rows if row["quadrant"] == "improving"]
        weakening = [row["sector"] for row in rows if row["quadrant"] == "weakening"]
        lagging = [row["sector"] for row in rows if row["quadrant"] == "lagging"]
        return {
            "leading_count": len(leading),
            "improving_count": len(improving),
            "weakening_count": len(weakening),
            "lagging_count": len(lagging),
            "top_leading": leading[:3],
            "top_improving": improving[:3],
            "top_weakening": weakening[:3],
            "top_lagging": lagging[:3],
        }

    @staticmethod
    def _industry_summary(rows: list[dict[str, object]]) -> dict[str, object]:
        reliable = [r for r in rows if r.get("reliable")]
        insufficient = [r for r in rows if not r.get("reliable") and r.get("status") == "Insufficient"]
        coverage_gaps = [r for r in rows if r.get("status") == "Coverage Gap"]
        unmapped_tickers = [ticker for row in coverage_gaps for ticker in row.get("tickers", [])]
        total_stocks = sum(int(r.get("stock_count") or 0) for r in rows)
        return {
            "strong_count": sum(1 for r in reliable if r.get("status") == "Strong"),
            "moderate_count": sum(1 for r in reliable if r.get("status") == "Moderate"),
            "weak_count": sum(1 for r in reliable if r.get("status") == "Weak"),
            "avoid_count": sum(1 for r in reliable if r.get("status") == "Avoid"),
            "insufficient_count": len(insufficient),
            "coverage_gap_count": len(unmapped_tickers),
            "coverage_gap_tickers": unmapped_tickers,
            "top_industry": reliable[0].get("industry") if reliable else None,
            "top_composite": reliable[0].get("composite") if reliable else 0.0,
            "avg_composite": round(float(np.mean([float(r.get("composite") or 0.0) for r in reliable])), 1) if reliable else 0.0,
            "total_stocks": total_stocks,
            "coverage_pct": round((1 - len(unmapped_tickers) / max(1, total_stocks)) * 100, 1),
        }

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
