"""Official EGX sector snapshot and loader (R44 D-9, R47 S1).

Sources (pages carry no effective date; both were read on ``FETCHED_ON`` by a human):

* S1 ``listedstocks.aspx`` ("All Listed Stocks"): company name, ISIN and sector for every
  listed stock; it has no ticker or Reuters column.
* S2 ``currentindexconstituntes.aspx?type=3`` (sectoral indices): ISIN + Reuters code per
  sector index, picked with an ASP.NET postback dropdown. These are not scripted.

Each row of ``SECTOR_ROWS`` joins one of our tickers to an EGX sector with a ``match_basis``:

* ``sector_index_reuters``: the S2 sector-index page lists the company's Reuters code.
* ``alias``: a reviewed ticker alias (ALRA in our DB is AIFI on EGX).
* ``name_review``: a human matched the company name against S1. Requires ``review_note``
  (the S1 name matched). Never fuzzy auto-matching.

Companies with no row (AREH, the junk ``RT9...`` test rows) keep no sector: UNKNOWN. The raw
sector name is never used as a Shariah industry (see ``app.screening.activity_tags``).

STATUS: ``SECTOR_ROWS`` holds the S1 rows the owner approved on 2026-10-30 (R47 S2), all
``name_review`` except the ALRA alias; S2 was not used. The saved page is in
``.workflow/research/egx-s1-listed-stocks-2026-10-30.tsv``. The loader refuses to run on an
empty snapshot rather than report a made-up success.

Usage:
    python -m app.industry.egx_sectors            # load the snapshot (idempotent)
    python -m app.industry.egx_sectors --check    # validate and print coverage, no DB
"""

import argparse
import asyncio
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.backfill import (
    BackfillReport,
    EgxListingRow,
    backfill_egx_sectors,
    normalize_sector_name,
)
from app.industry.constants import EGX_LISTED_STOCKS_URL, EGX_SECTOR_NAMES

logger = logging.getLogger(__name__)

SOURCE_URLS: tuple[str, ...] = (
    EGX_LISTED_STOCKS_URL,
    "https://www.egx.com.eg/en/currentindexconstituntes.aspx?type=3&nav=3",
)
FETCHED_ON = date(2026, 10, 30)
SNAPSHOT_NOTE = (
    f"EGX listed-stocks and sector-index pages read {FETCHED_ON.isoformat()}; the pages carry "
    "no effective date, so sector assignments can drift with index reviews. Sector names are "
    "normalised ('Industrial Goods , Services' to 'Industrial Goods, Services')."
)

BASIS_SECTOR_INDEX = "sector_index_reuters"
BASIS_ALIAS = "alias"
BASIS_NAME_REVIEW = "name_review"
MATCH_BASES: frozenset[str] = frozenset({BASIS_SECTOR_INDEX, BASIS_ALIAS, BASIS_NAME_REVIEW})


@dataclass(frozen=True, slots=True)
class SectorRow:
    """One literal snapshot row: our ticker, the EGX ISIN, the EGX sector and how they match."""

    ticker: str
    isin: str
    egx_sector: str
    match_basis: str
    #: Required for ``name_review``: the S1 company name the reviewer matched.
    review_note: str | None = None


#: Rows matched by name against S1 (read 2026-10-30) and approved by the owner (R47 S2).
#: review_note is the S1 company name. Held back until the listing is confirmed: SEIG/SEIGA
#: (our currency records conflict with S1's EGP and '$' lines) and VLMR/VLMRA (no currency).
SECTOR_ROWS: tuple[SectorRow, ...] = (
    SectorRow(
        "AALR",
        "EGS01081C016",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "General Company For Land Reclamation,Development & Reconstru",
    ),
    SectorRow("ABUK", "EGS38191C010", "Basic Resources", BASIS_NAME_REVIEW, "Abou Kir Fertilizers"),
    SectorRow(
        "ACAMD",
        "EGS72AQ1C016",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Arab Co. for Asset Management And Development",
    ),
    SectorRow("ACAP", "EGS697S1C015", "Real Estate", BASIS_NAME_REVIEW, "A Capital Holding"),
    SectorRow(
        "ACGC", "EGS32221C011", "Textile & Durables", BASIS_NAME_REVIEW, "Arab Cotton Ginning"
    ),
    SectorRow(
        "ACTF", "EGS7D5P1C019", "Non-bank financial services", BASIS_NAME_REVIEW, "Act Financial"
    ),
    SectorRow(
        "ADCI",
        "EGS38321C013",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Arab Pharmaceuticals",
    ),
    SectorRow("ADIB", "EGS60111C019", "Banks", BASIS_NAME_REVIEW, "Abu Dhabi Islamic Bank- Egypt"),
    SectorRow(
        "ADPC",
        "EGS30221C013",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "The Arab Dairy Products Co. Arab Dairy - Panda",
    ),
    SectorRow(
        "AFDI",
        "EGS69021C011",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "El Ahli Investment and Development",
    ),
    SectorRow(
        "AFMC",
        "EGS30471C014",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Alexandria Flour Mills",
    ),
    SectorRow(
        "AIDC",
        "EGS65R01C015",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Arabia for Investment and Development",
    ),
    SectorRow(
        "AIHC",
        "EGS21351C019",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Arabia Investments Holding",
    ),
    SectorRow(
        "AJWA",
        "EGS30211C014",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "AJWA for Food Industries company Egypt",
    ),
    SectorRow(
        "ALCN",
        "EGS42111C012",
        "Shipping & Transportation Services",
        BASIS_NAME_REVIEW,
        "Alexandria Containers and goods",
    ),
    SectorRow(
        "ALRA",
        "EGS071L1C018",
        "Real Estate",
        BASIS_ALIAS,
        "Atlas For Investment and Food Industries",
    ),
    SectorRow("ALUM", "EGS3D031C018", "Basic Resources", BASIS_NAME_REVIEW, "Arab Aluminum"),
    SectorRow("AMER", "EGS675S1C011", "Real Estate", BASIS_NAME_REVIEW, "Amer Group Holding"),
    SectorRow(
        "AMES",
        "EGS72081C010",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Alexandria New Medical Center",
    ),
    SectorRow(
        "AMIA",
        "EGS67221C019",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Arab Moltaka Investments Co",
    ),
    SectorRow(
        "AMII",
        "EGS3E1E1C013",
        "Building Materials",
        BASIS_NAME_REVIEW,
        "Arabian Metal Industries And Industrial Investments",
    ),
    SectorRow(
        "AMOC",
        "EGS380P1C010",
        "Energy & Support Services",
        BASIS_NAME_REVIEW,
        "Alexandria Mineral Oils Company",
    ),
    SectorRow(
        "APSW",
        "EGS32331C018",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "ARAB POLVARA SPINNING & WEAVING CO.",
    ),
    SectorRow("ARAB", "EGS694A1C018", "Real Estate", BASIS_NAME_REVIEW, "Arab Developers Holding"),
    SectorRow(
        "ARCC", "EGS3C0O1C016", "Building Materials", BASIS_NAME_REVIEW, "Arabian Cement Company"
    ),
    SectorRow(
        "ASCM",
        "EGS10001C013",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "ASEC Company For Mining - ASCOM",
    ),
    SectorRow(
        "ASPI",
        "EGS691L1C018",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Aspire Capital Holding For Financial Investments",
    ),
    SectorRow(
        "ATLC",
        "EGS676N1C015",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Al Tawfeek Leasing Company-A.T.LEASE",
    ),
    SectorRow(
        "ATQA", "EGS3D0C1C018", "Basic Resources", BASIS_NAME_REVIEW, "Misr National Steel - Ataqa"
    ),
    SectorRow(
        "AXPH",
        "EGS38341C011",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Alexandria Pharmaceuticals",
    ),
    SectorRow(
        "BINV",
        "EGS691T1C010",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "B Investments Holding",
    ),
    SectorRow(
        "BIOC",
        "EGS38171C012",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Glaxo Smith Kline",
    ),
    SectorRow(
        "BONY", "EGS656M1C010", "Real Estate", BASIS_NAME_REVIEW, "Bonyan for Development and Trade"
    ),
    SectorRow(
        "BTFH", "EGS691G1C015", "Non-bank financial services", BASIS_NAME_REVIEW, "Beltone Holding"
    ),
    SectorRow(
        "CAED",
        "EGS72201C014",
        "Education Services",
        BASIS_NAME_REVIEW,
        "Cairo Educational Services",
    ),
    SectorRow("CANA", "EGS60231C015", "Banks", BASIS_NAME_REVIEW, "Suez Canal Bank S.A.E"),
    SectorRow(
        "CCAP",
        "EGS73541C012",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "QALAA For Financial Investments",
    ),
    SectorRow(
        "CCRS",
        "EGS651B1C018",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Gulf Canadian Real Estate Investment Co.",
    ),
    SectorRow(
        "CEFM",
        "EGS30401C011",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Middle Egypt Flour Mills",
    ),
    SectorRow(
        "CERA",
        "EGS3C151C015",
        "Building Materials",
        BASIS_NAME_REVIEW,
        "The Arab Ceramic CO.- Ceramica Remas",
    ),
    SectorRow(
        "CFGH",
        "EGS672I2C014",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "Concrete Fashion Group For Commercial& Industrial Investment",
    ),
    SectorRow(
        "CICH",
        "EGS691D1C018",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "CI Capital Holding For Financial Investments",
    ),
    SectorRow("CIEB", "EGS60041C018", "Banks", BASIS_NAME_REVIEW, "Credit Agricole Egypt"),
    SectorRow(
        "CIRA",
        "EGS65541C012",
        "Education Services",
        BASIS_NAME_REVIEW,
        "Cairo For Investment And Real Estate Developments-CIRA Edu",
    ),
    SectorRow(
        "CLHO",
        "EGS729J1C018",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Cleopatra Hospital Company",
    ),
    SectorRow(
        "CNFN",
        "EGS738I1C018",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Contact Financial Holding",
    ),
    SectorRow(
        "COMI",
        "EGS60121C018",
        "Banks",
        BASIS_NAME_REVIEW,
        "Commercial International Bank-Egypt (CIB)",
    ),
    SectorRow(
        "COPR",
        "EGS65511C015",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Copper For Commercial Investment & Real Estate Development",
    ),
    SectorRow(
        "COSG",
        "EGS30581C010",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Cairo Oils & Soap",
    ),
    SectorRow(
        "CPCI",
        "EGS38391C016",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Cairo Pharmaceuticals",
    ),
    SectorRow(
        "CPME",
        "EGS698X1C017",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Catalyst Partners Middle East –CPME",
    ),
    SectorRow(
        "CRST",
        "EGS23141C012",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Creast Mark For Contracting And Real Estate Development",
    ),
    SectorRow(
        "CSAG",
        "EGS44031C010",
        "Shipping & Transportation Services",
        BASIS_NAME_REVIEW,
        "Canal Shipping Agencies",
    ),
    SectorRow(
        "DAPH",
        "EGS65081C019",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Development & Engineering Consultants",
    ),
    SectorRow(
        "DCCC",
        "EGS42121C011",
        "Shipping & Transportation Services",
        BASIS_NAME_REVIEW,
        "Damietta Container and Cargo Handling",
    ),
    SectorRow(
        "DEIN", "EGS63031C016", "Non-bank financial services", BASIS_NAME_REVIEW, "Delta Insurance"
    ),
    SectorRow(
        "DGTZ",
        "EGS74F71C015",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Digitize for Investment And Technology",
    ),
    SectorRow(
        "DOMT",
        "EGS30031C016",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Arabian Food Industries DOMTY",
    ),
    SectorRow(
        "DSCW", "EGS33321C018", "Textile & Durables", BASIS_NAME_REVIEW, "Dice Sport & Casual Wear"
    ),
    SectorRow(
        "DTPP",
        "EGS370W1C013",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "Delta For Printing & Packaging",
    ),
    SectorRow(
        "EALR",
        "EGS65771C015",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "El Arabia for Land Reclamation",
    ),
    SectorRow(
        "EASB",
        "EGS681D1C010",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Egyptian Arabian(Themar)Comp. For Securities&Bonds Brok. EAC",
    ),
    SectorRow(
        "EAST", "EGS37091C013", "Food, Beverages and Tobacco", BASIS_NAME_REVIEW, "Eastern Company"
    ),
    SectorRow(
        "EBSC",
        "EGS68181C014",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Osool ESB Securities Brokerage",
    ),
    SectorRow(
        "ECAP", "EGS3C071C015", "Building Materials", BASIS_NAME_REVIEW, "El Ezz Porcelain (Gemma)"
    ),
    SectorRow(
        "EDFM",
        "EGS30351C018",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "East Delta Flour Mills",
    ),
    SectorRow(
        "EEII",
        "EGS3G111C015",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "El Arabia Engineering Industries",
    ),
    SectorRow(
        "EFIC",
        "EGS38381C017",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "Egyptian Financial & Industrial",
    ),
    SectorRow(
        "EFID",
        "EGS305I1C011",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Edita Food Industries S.A.E",
    ),
    SectorRow(
        "EFIH",
        "EGS743O1C013",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "E-finance For Digital and Financial Investments",
    ),
    SectorRow("EGAL", "EGS3E181C010", "Basic Resources", BASIS_NAME_REVIEW, "Egypt Aluminum"),
    SectorRow(
        "EGAS",
        "EGS39011C019",
        "Utilities",
        BASIS_NAME_REVIEW,
        "Natural Gas & Mining Project (Egypt Gas)",
    ),
    SectorRow("EGBE", "EGS60182C010", "Banks", BASIS_NAME_REVIEW, "Egyptian Gulf Bank"),
    SectorRow(
        "EGCH",
        "EGS38201C017",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "Egyptian Chemical Industries (Kima)",
    ),
    SectorRow(
        "EGSA",
        "EGS48022C015",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Egyptian Satellites (NileSat)",
    ),
    SectorRow(
        "EGTS",
        "EGS70431C019",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "Egyptian for Tourism Resorts",
    ),
    SectorRow(
        "EHDR",
        "EGS65341C017",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Egyptians Housing Development & Reconstruction",
    ),
    SectorRow(
        "ELEC",
        "EGS3G231C011",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "Electro Cable Egypt",
    ),
    SectorRow("ELKA", "EGS65071C010", "Real Estate", BASIS_NAME_REVIEW, "El Kahera Housing"),
    SectorRow(
        "ELNA",
        "EGS300L1C011",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "El Nasr For Manufacturing Agricultural Crops",
    ),
    SectorRow(
        "ELSH", "EGS65091C018", "Real Estate", BASIS_NAME_REVIEW, "El Shams Housing & Urbanization"
    ),
    SectorRow(
        "ELWA",
        "EGS70R91C016",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "El Wadi For International and Investement Development",
    ),
    SectorRow(
        "EMFD", "EGS673Y1C015", "Real Estate", BASIS_NAME_REVIEW, "Emaar Misr for Development"
    ),
    SectorRow(
        "ENGC",
        "EGS3F021C017",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Engineering Industries (ICON)",
    ),
    SectorRow(
        "EOSB",
        "EGS681I1C015",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "El Orouba Securities Brokerage",
    ),
    SectorRow(
        "EPCO",
        "EGS02211C018",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Egypt for Poultry",
    ),
    SectorRow(
        "EPPK",
        "EGS360A1C011",
        "Paper & Packaging",
        BASIS_NAME_REVIEW,
        "El Ahram Co. For Printing And Packing",
    ),
    SectorRow(
        "ETEL",
        "EGS48031C016",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Telecom Egypt",
    ),
    SectorRow(
        "ETRS",
        "EGS42051C010",
        "Shipping & Transportation Services",
        BASIS_NAME_REVIEW,
        "Egyptian Transport & Commercial Services Co. -EGYTRANS NOSCO",
    ),
    SectorRow(
        "EXPA", "EGS60241C014", "Banks", BASIS_NAME_REVIEW, "Export Development Bank of Egypt"
    ),
    SectorRow(
        "FAIT", "EGS60321C014", "Banks", BASIS_NAME_REVIEW, "Faisal Islamic Bank of Egypt - In EGP"
    ),
    SectorRow(
        "FAITA",
        "EGS60322C012",
        "Banks",
        BASIS_NAME_REVIEW,
        "Faisal Islamic Bank of Egypt - In US Dollars",
    ),
    SectorRow(
        "FCMD",
        "EGS3I0S1C019",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Future Care for Medical Industries - FCMI",
    ),
    SectorRow(
        "FERC",
        "EGS385S1C012",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "FERCHEM MISR CO. FOR FERTILLIZERS & CHEMICALS",
    ),
    SectorRow(
        "FWRY",
        "EGS745L1C014",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Fawry For Banking Technology And Electronic Payment",
    ),
    SectorRow(
        "GBCO",
        "EGS673T1C012",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "GB Corp",
    ),
    SectorRow(
        "GDWA",
        "EGS3JM11C012",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "Gadwa For Industrial Development",
    ),
    SectorRow(
        "GGCC",
        "EGS21541C015",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Giza General Contracting",
    ),
    SectorRow(
        "GGRN",
        "EGS07DR1C012",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Gogreen for Agricultural Investment",
    ),
    SectorRow(
        "GIHD",
        "EGS65461C013",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Gharbia Islamic Housing Development",
    ),
    SectorRow(
        "GMCI",
        "EGS46051C016",
        "Trade & Distributors",
        BASIS_NAME_REVIEW,
        "GMC GROUP FOR INDUSTRIAL COMMERCIAL & FINANCIAL INVESTMENTS",
    ),
    SectorRow(
        "GOUR", "EGS540S1C014", "Trade & Distributors", BASIS_NAME_REVIEW, "Gourmet Egypt.Com Foods"
    ),
    SectorRow(
        "GPIM",
        "EGS213S1C010",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "GPI For Urban Growth",
    ),
    SectorRow(
        "GPPL", "EGS70342C018", "Travel & Leisure", BASIS_NAME_REVIEW, "Golden Pyramids Plaza"
    ),
    SectorRow(
        "GRCA",
        "EGS69261C013",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Grand Investment Capital",
    ),
    SectorRow(
        "GSSC",
        "EGS30441C017",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "General Silos & Storage",
    ),
    SectorRow(
        "GTEX",
        "EGS59U92C011",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "GTEX For Commercial And Industrial",
    ),
    SectorRow(
        "GTWL",
        "EGS32161C019",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "Golden Textiles & Clothes Wool",
    ),
    SectorRow(
        "HALN",
        "EGS59231C018",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "MNT Tech Holding For Financial Investments",
    ),
    SectorRow("HDBK", "EGS60301C016", "Banks", BASIS_NAME_REVIEW, "Housing & Development Bank"),
    SectorRow("HELI", "EGS65591C017", "Real Estate", BASIS_NAME_REVIEW, "Heliopolis Housing"),
    SectorRow(
        "HRHO", "EGS69101C011", "Non-bank financial services", BASIS_NAME_REVIEW, "EFG Holding"
    ),
    SectorRow(
        "ICFC",
        "EGS520D1C015",
        "Trade & Distributors",
        BASIS_NAME_REVIEW,
        "International Company For Fertilizers & Chemicals",
    ),
    SectorRow(
        "ICID",
        "EGS67191C014",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "International Co For Investment & Development",
    ),
    SectorRow(
        "ICLE",
        "EGS67001C015",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "International Company For Leasing (IncoLEASE)",
    ),
    SectorRow(
        "IDRE",
        "EGS214Q1C011",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Ismailia Development and Real Estate Co",
    ),
    SectorRow(
        "IEEC",
        "EGS22171C010",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Industrial & Engineering Projects",
    ),
    SectorRow(
        "IFAP",
        "EGS07061C012",
        "Trade & Distributors",
        BASIS_NAME_REVIEW,
        "International Agricultural Products",
    ),
    SectorRow(
        "INFI",
        "EGS01041C010",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Ismailia National Food Industries",
    ),
    SectorRow(
        "IRON", "EGS3D061C015", "Basic Resources", BASIS_NAME_REVIEW, "Egyptian Iron & Steel"
    ),
    SectorRow(
        "ISMA",
        "EGS02021C011",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Ismailia Misr Poultry",
    ),
    SectorRow(
        "ISMQ",
        "EGS102S1C014",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "Iron And Steel for Mines and Quarries",
    ),
    SectorRow(
        "ISPH", "EGS512O1C012", "Health Care & Pharmaceuticals", BASIS_NAME_REVIEW, "Ibnsina Pharma"
    ),
    SectorRow(
        "JUFO",
        "EGS30901C010",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Juhayna Food Industries",
    ),
    SectorRow(
        "KABO",
        "EGS33061C010",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "El Nasr Clothes & Textiles (Kabo)",
    ),
    SectorRow(
        "KORA", "EGS07911C018", "Contracting & Construction Engineering", BASIS_NAME_REVIEW, "KORRA"
    ),
    SectorRow(
        "KRDI",
        "EGS02291C010",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Al Khair River For Development Agricultural Investment&Envir",
    ),
    SectorRow(
        "KWIN",
        "EGS69011C012",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "El Kahera El Watania Investment",
    ),
    SectorRow(
        "KZPC", "EGS38411C012", "Basic Resources", BASIS_NAME_REVIEW, "Kafr El Zayat Pesticides"
    ),
    SectorRow("LCSW", "EGS3C161C014", "Building Materials", BASIS_NAME_REVIEW, "Lecico Egypt"),
    SectorRow(
        "LUTS",
        "EGS07661C019",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Lotus For Agricultural Investments And Development",
    ),
    SectorRow(
        "MAAL",
        "EGS739Z1C016",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Egyptian Gulf Marseilia For Real Estate Investment",
    ),
    SectorRow(
        "MASR",
        "EGS65571C019",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Madinet Masr For Housing and Development",
    ),
    SectorRow(
        "MBEG",
        "EGS221V1C015",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "M.B Engineering",
    ),
    SectorRow(
        "MBSC", "EGS3C371C019", "Building Materials", BASIS_NAME_REVIEW, "Misr Beni Suef Cement"
    ),
    SectorRow(
        "MCQE", "EGS3C391C017", "Building Materials", BASIS_NAME_REVIEW, "Misr Cement (Qena)"
    ),
    SectorRow(
        "MCRO",
        "EGS7D971C011",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Macro Group Pharmaceuticals -Macro Capital",
    ),
    SectorRow(
        "MEGM",
        "EGS3C001C012",
        "Paper & Packaging",
        BASIS_NAME_REVIEW,
        "Middle East Glass Manufacturing",
    ),
    SectorRow(
        "MENA",
        "EGS65441C015",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Mena Touristic & Real Estate Investment",
    ),
    SectorRow(
        "MEPA",
        "EGS3C4L1C015",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Medical Packaging Company",
    ),
    SectorRow(
        "MFPC",
        "EGS39061C014",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "Misr Fertilizers Production Company - Mopco",
    ),
    SectorRow(
        "MFSC", "EGS53051C016", "Trade & Distributors", BASIS_NAME_REVIEW, "Misr Duty Free Shops"
    ),
    SectorRow("MHOT", "EGS70081C012", "Travel & Leisure", BASIS_NAME_REVIEW, "Misr Hotels"),
    SectorRow(
        "MICH", "EGS38211C016", "Basic Resources", BASIS_NAME_REVIEW, "Misr Chemical Industries"
    ),
    SectorRow(
        "MILS",
        "EGS30361C017",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "North Cairo Mills",
    ),
    SectorRow(
        "MIPH",
        "EGS380G1C011",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Minapharm Pharmaceuticals",
    ),
    SectorRow(
        "MMAT",
        "EGS70P91C010",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "Marsa Marsa Alam For Tourism Development",
    ),
    SectorRow(
        "MOED",
        "EGS729F1C012",
        "Education Services",
        BASIS_NAME_REVIEW,
        "The Egyptian Modern Education Systems",
    ),
    SectorRow(
        "MOIL",
        "EGS44012C010",
        "Energy & Support Services",
        BASIS_NAME_REVIEW,
        "Maridive & oil services",
    ),
    SectorRow(
        "MOIN",
        "EGS63041C015",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Mohandes Insurance",
    ),
    SectorRow(
        "MOSC", "EGS38421C011", "Food, Beverages and Tobacco", BASIS_NAME_REVIEW, "Misr Oils & Soap"
    ),
    SectorRow(
        "MPCI",
        "EGS38351C010",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Memphis Pharmaceuticals",
    ),
    SectorRow(
        "MPCO",
        "EGS02091C014",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Mansourah Poultry",
    ),
    SectorRow(
        "MPRC",
        "EGS78021C010",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Egyptian Media Production City",
    ),
    SectorRow(
        "MTIE",
        "EGS75011C014",
        "Trade & Distributors",
        BASIS_NAME_REVIEW,
        "MM Group For Industry And International Trade",
    ),
    SectorRow(
        "NAHO", "EGS69182C011", "Non-bank financial services", BASIS_NAME_REVIEW, "Naeem Holding"
    ),
    SectorRow("NAPR", "EGS370O1C013", "Paper & Packaging", BASIS_NAME_REVIEW, "National Printing"),
    SectorRow(
        "NARE", "EGS69191C012", "Real Estate", BASIS_NAME_REVIEW, "Naeem Real Estate Holding Group"
    ),
    SectorRow(
        "NCCW",
        "EGS23111C015",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Nasr Company for Civil Works",
    ),
    SectorRow(
        "NDRL", "EGS735N2C012", "Energy & Support Services", BASIS_NAME_REVIEW, "National Drilling"
    ),
    SectorRow(
        "NEDA",
        "EGS52041C018",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Northern Upper Egypt Development & Agricultural Production",
    ),
    SectorRow(
        "NHPS",
        "EGS65131C012",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "National Housing for Professional Syndicates",
    ),
    SectorRow(
        "NINH",
        "EGS72011C017",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Nozha International Hospital",
    ),
    SectorRow(
        "NIPH",
        "EGS38331C012",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "El-Nile Co. For Pharmaceuticals And Chemical Industries",
    ),
    SectorRow(
        "OBRI", "EGS65551C011", "Real Estate", BASIS_NAME_REVIEW, "El Obour Real Estate Investment"
    ),
    SectorRow(
        "OCDI",
        "EGS65851C015",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Six of October Development & Investment (SODIC)",
    ),
    SectorRow(
        "OCPH", "EGS380R1C018", "Health Care & Pharmaceuticals", BASIS_NAME_REVIEW, "October Pharma"
    ),
    SectorRow(
        "ODIN", "EGS67181C015", "Non-bank financial services", BASIS_NAME_REVIEW, "ODIN Investments"
    ),
    SectorRow(
        "OFH",
        "EGS696S1C016",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "O B Financial Holding",
    ),
    SectorRow(
        "OIH",
        "EGS693V1C014",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Orascom Investment Holding",
    ),
    SectorRow(
        "OLFI",
        "EGS30AL1C012",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Obour Land For Food Industries",
    ),
    SectorRow(
        "ORAS",
        "EGS95001C011",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Orascom Construction PLC",
    ),
    SectorRow(
        "ORHD", "EGS70321C012", "Real Estate", BASIS_NAME_REVIEW, "Orascom Development Egypt"
    ),
    SectorRow("ORWE", "EGS33041C012", "Textile & Durables", BASIS_NAME_REVIEW, "Oriental Weavers"),
    SectorRow(
        "PHAR",
        "EGS38081C013",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Egyptian International Pharmaceuticals (EIPICO)",
    ),
    SectorRow(
        "PHDC", "EGS655L1C012", "Real Estate", BASIS_NAME_REVIEW, "Palm Hills Development Company"
    ),
    SectorRow(
        "PHGC",
        "EGS72XL1C014",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Premium HealthCare Group",
    ),
    SectorRow("PHTV", "EGS70331C011", "Travel & Leisure", BASIS_NAME_REVIEW, "Pyramisa Hotels"),
    SectorRow(
        "POCO",
        "EGS42101C013",
        "Shipping & Transportation Services",
        BASIS_NAME_REVIEW,
        "Port Said Containers And Cargo Handling Co.",
    ),
    SectorRow(
        "POUL", "EGS02051C018", "Food, Beverages and Tobacco", BASIS_NAME_REVIEW, "Cairo Poultry"
    ),
    SectorRow(
        "PRCL", "EGS3C111C019", "Building Materials", BASIS_NAME_REVIEW, "Ceramic & Porcelain"
    ),
    SectorRow(
        "PRDC",
        "EGS21FW1C015",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Pioneers Properties For Urban Development - PRE Group",
    ),
    SectorRow(
        "PRMH", "EGS691A1C011", "Non-bank financial services", BASIS_NAME_REVIEW, "Prime Holding"
    ),
    SectorRow("QNBE", "EGS60081C014", "Banks", BASIS_NAME_REVIEW, "Qatar National Bank"),
    SectorRow(
        "RACC",
        "EGS74191C015",
        "IT, Media & Communication Services",
        BASIS_NAME_REVIEW,
        "Raya Customer Experience",
    ),
    SectorRow(
        "RAKT", "EGS36021C011", "Paper & Packaging", BASIS_NAME_REVIEW, "Rakta Paper Manufacturing"
    ),
    SectorRow(
        "RAYA",
        "EGS690C1C010",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Raya Holding For Financial Investments",
    ),
    SectorRow(
        "RMDA",
        "EGS381B1C015",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Tenth Of Ramadan Pharmaceutical Industries&Diagnostic-Rameda",
    ),
    SectorRow(
        "ROTO", "EGS70281C018", "Travel & Leisure", BASIS_NAME_REVIEW, "Rowad Tourism (Al Rowad)"
    ),
    SectorRow(
        "RREI",
        "EGS65011C016",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Arab Real Estate Investment CO.-ALICO",
    ),
    SectorRow(
        "RTVC",
        "EGS70271C019",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "Remco for Touristic Villages Construction",
    ),
    SectorRow(
        "RUBX",
        "EGS3A221C018",
        "Building Materials",
        BASIS_NAME_REVIEW,
        "Rubex International for Plastic and Acrylic Manufacturing",
    ),
    SectorRow(
        "SAIB",
        "EGS60142C014",
        "Banks",
        BASIS_NAME_REVIEW,
        "Societe Arabe Internationale De Banque S.A.E.",
    ),
    SectorRow("SAUD", "EGS60101C010", "Banks", BASIS_NAME_REVIEW, "Al Baraka Bank Egypt"),
    SectorRow("SCEM", "EGS3C401C014", "Building Materials", BASIS_NAME_REVIEW, "Sinai Cement"),
    SectorRow(
        "SCFM",
        "EGS30411C010",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "South Cairo & Giza Mills & Bakeries",
    ),
    SectorRow(
        "SCTS",
        "EGS740C1C010",
        "Education Services",
        BASIS_NAME_REVIEW,
        "Sues Canal Company For Technology Settling",
    ),
    SectorRow(
        "SDTI",
        "EGS70571C012",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "Sharm Dreams Co. for Tourism Investment",
    ),
    SectorRow(
        "SIPC",
        "EGS382M1C011",
        "Health Care & Pharmaceuticals",
        BASIS_NAME_REVIEW,
        "Sabaa International Company for Pharmaceutical and Chemical",
    ),
    SectorRow(
        "SKPC",
        "EGS380S1C017",
        "Basic Resources",
        BASIS_NAME_REVIEW,
        "Sidi Kerir Petrochemicals - SIDPEC",
    ),
    SectorRow(
        "SMFR", "EGS51191C012", "Trade & Distributors", BASIS_NAME_REVIEW, "Samad Misr -EGYFERT"
    ),
    SectorRow(
        "SNFC",
        "EGS30291C016",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Sharkia National Food",
    ),
    SectorRow(
        "SPHT",
        "EGS70H02C014",
        "Travel & Leisure",
        BASIS_NAME_REVIEW,
        "El Shams Pyramids For Hotels& Touristic Projects",
    ),
    SectorRow(
        "SPIN",
        "EGS32041C013",
        "Textile & Durables",
        BASIS_NAME_REVIEW,
        "Alexandria Spinning & Weaving (SPINALEX)",
    ),
    SectorRow(
        "SPMD", "EGS73BR1C013", "Health Care & Pharmaceuticals", BASIS_NAME_REVIEW, "Speed Medical"
    ),
    SectorRow(
        "SUGR", "EGS30201C015", "Food, Beverages and Tobacco", BASIS_NAME_REVIEW, "Delta Sugar"
    ),
    SectorRow(
        "SVCE", "EGS3C351C011", "Building Materials", BASIS_NAME_REVIEW, "South Valley Cement"
    ),
    SectorRow(
        "SWDY",
        "EGS3G0Z1C014",
        "Industrial Goods, Services and Automobiles",
        BASIS_NAME_REVIEW,
        "ELSWEDY ELECTRIC",
    ),
    SectorRow(
        "TALM",
        "EGS597R1C017",
        "Education Services",
        BASIS_NAME_REVIEW,
        "Taaleem Management Services",
    ),
    SectorRow(
        "TANM",
        "EGS21EB1C011",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Tanmiya for Real Estate Investment",
    ),
    SectorRow("TAQA", "EGS490S1C014", "Utilities", BASIS_NAME_REVIEW, "Taqa Arabia"),
    SectorRow("TMGH", "EGS691S1C011", "Real Estate", BASIS_NAME_REVIEW, "T M G Holding"),
    SectorRow("TRTO", "EGS79072C012", "Travel & Leisure", BASIS_NAME_REVIEW, "TransOceans Tours"),
    SectorRow(
        "TWSA",
        "EGS7D231C010",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "TAWASOA For Factoring",
    ),
    SectorRow(
        "TYCN",
        "EGS67331C016",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "Tycoon Holding Company For Financial Investments",
    ),
    SectorRow("UBEE", "EGS600M1C017", "Banks", BASIS_NAME_REVIEW, "The United Bank"),
    SectorRow(
        "UEFM",
        "EGS30451C016",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Upper Egypt Flour Mills",
    ),
    SectorRow(
        "UEGC",
        "EGS21531C016",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Elsaeed Contracting& Real Estate Investment Company SCCD",
    ),
    SectorRow(
        "UNIP",
        "EGS38161C013",
        "Paper & Packaging",
        BASIS_NAME_REVIEW,
        "Universal For Paper and Packaging Materials (Unipack",
    ),
    SectorRow(
        "UNIT", "EGS65061C011", "Real Estate", BASIS_NAME_REVIEW, "United Housing & Development"
    ),
    SectorRow(
        "VALU",
        "EGS505Z1C018",
        "Non-bank financial services",
        BASIS_NAME_REVIEW,
        "U Consumer Finance",
    ),
    SectorRow(
        "WCDF",
        "EGS30421C019",
        "Food, Beverages and Tobacco",
        BASIS_NAME_REVIEW,
        "Middle & West Delta Flour Mills",
    ),
    SectorRow(
        "WKOL",
        "EGS01071C017",
        "Contracting & Construction Engineering",
        BASIS_NAME_REVIEW,
        "Wadi Kom Ombo Land Reclamation",
    ),
    SectorRow(
        "ZEOT", "EGS38251C012", "Food, Beverages and Tobacco", BASIS_NAME_REVIEW, "Extracted Oils"
    ),
    SectorRow(
        "ZMID",
        "EGS21171C011",
        "Real Estate",
        BASIS_NAME_REVIEW,
        "Zahraa Maadi Investment & Development",
    ),
)

#: Our DB tickers that must stay without a sector (R44 D-9: AREH has no S1 match).
UNASSIGNED_TICKERS: frozenset[str] = frozenset({"AREH"})


def validate_rows(rows: tuple[SectorRow, ...]) -> list[str]:
    """Return a list of problems; empty = the snapshot is loadable."""
    problems: list[str] = []
    known = {normalize_sector_name(n) for n in EGX_SECTOR_NAMES}
    seen_tickers: set[str] = set()
    seen_isins: set[str] = set()
    for row in rows:
        label = row.ticker or "<blank ticker>"
        if not row.ticker.strip() or row.ticker != row.ticker.strip().upper():
            problems.append(f"{label}: ticker must be upper-case and non-blank")
        if len(row.isin) != 12:
            problems.append(f"{label}: ISIN '{row.isin}' is not 12 characters")
        if normalize_sector_name(row.egx_sector) not in known:
            problems.append(f"{label}: unknown EGX sector '{row.egx_sector}'")
        if row.match_basis not in MATCH_BASES:
            problems.append(
                f"{label}: match_basis '{row.match_basis}' not in {sorted(MATCH_BASES)}"
            )
        if row.match_basis == BASIS_NAME_REVIEW and not (row.review_note or "").strip():
            problems.append(f"{label}: name_review needs a review_note (the S1 name matched)")
        if row.ticker in UNASSIGNED_TICKERS:
            problems.append(f"{label}: must stay without a sector")
        if row.ticker in seen_tickers:
            problems.append(f"{label}: duplicate ticker")
        if row.isin in seen_isins:
            problems.append(f"{label}: duplicate ISIN {row.isin}")
        seen_tickers.add(row.ticker)
        seen_isins.add(row.isin)
    return problems


def coverage(rows: tuple[SectorRow, ...]) -> dict[str, dict[str, int]]:
    """Counts by match basis and by (normalised) sector, straight from the snapshot."""
    return {
        "by_match_basis": dict(Counter(r.match_basis for r in rows)),
        "by_sector": dict(Counter(normalize_sector_name(r.egx_sector) for r in rows)),
    }


def to_listing_rows(rows: tuple[SectorRow, ...]) -> list[EgxListingRow]:
    return [
        EgxListingRow(
            isin=r.isin,
            reuters_code=f"{r.ticker}.CA",
            sector_name=normalize_sector_name(r.egx_sector),
            match_basis=r.match_basis,
        )
        for r in rows
    ]


async def load_snapshot(
    session: AsyncSession, rows: tuple[SectorRow, ...] = SECTOR_ROWS
) -> BackfillReport:
    """Apply the snapshot (idempotent; flush only, caller commits).

    Raises ``ValueError`` on an empty or invalid snapshot: nothing is written.
    """
    if not rows:
        raise ValueError(
            "SECTOR_ROWS is empty: the EGX pages have not been transcribed; nothing loaded"
        )
    problems = validate_rows(rows)
    if problems:
        raise ValueError("invalid sector snapshot: " + "; ".join(problems))
    return await backfill_egx_sectors(
        session, to_listing_rows(rows), source_url=SOURCE_URLS[0], as_of=FETCHED_ON
    )


async def _main(check_only: bool) -> None:
    problems = validate_rows(SECTOR_ROWS)
    print(f"EGX sector snapshot {FETCHED_ON.isoformat()}: {len(SECTOR_ROWS)} rows")
    print(f"Coverage: {coverage(SECTOR_ROWS)}")
    if problems:
        print("Problems:\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    if not SECTOR_ROWS:
        print("SECTOR_ROWS is empty: nothing to load.")
        raise SystemExit(1)
    if check_only:
        return

    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        report = await load_snapshot(session)
        await session.commit()
    print(f"Updated {report.updated} companies; skipped {len(report.skipped)}")
    for skipped in report.skipped:
        print(f"  skipped {skipped.isin} {skipped.reuters_code}: {skipped.reason}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--check", action="store_true", help="validate only; no DB writes")
    asyncio.run(_main(parser.parse_args().check))
