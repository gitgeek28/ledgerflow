"""Fictional reference data for the demo buyer, Kestrel Components Pvt Ltd (Pune, India).

Single source of truth for the database seed AND the synthetic invoice-PDF generator, so documents and
master data stay consistent. All names, identifiers and bank details are invented for this case study.
"""
from dataclasses import dataclass, field
from datetime import date

BUYER = {
    "name": "Kestrel Components Pvt Ltd",
    "address": "Plot 42, MIDC Bhosari, Pune, Maharashtra 411026",
    "gstin_pan": "AAGCK4821M",
    "state_code": "27",
}

USERS = [
    {"email": "aisha.rao@kestrel.example", "name": "Aisha Rao", "title": "AP Analyst", "role": "AP_ANALYST"},
    {"email": "rohan.desai@kestrel.example", "name": "Rohan Desai", "title": "AP Analyst", "role": "AP_ANALYST"},
    {"email": "vikram.iyer@kestrel.example", "name": "Vikram Iyer", "title": "AP Manager", "role": "AP_MANAGER"},
    {"email": "meera.joshi@kestrel.example", "name": "Meera Joshi", "title": "Internal Auditor",
     "role": "AUDITOR"},
]


@dataclass
class Item:
    description: str
    unit: str
    price: str
    tax_rate: str
    hsn: str
    item_code: str | None = None


@dataclass
class VendorDef:
    code: str
    legal_name: str
    display_name: str
    aliases: list[str]
    pan: str
    state_code: str
    city: str
    address: str
    status: str
    category: str
    terms: int
    bank_name: str
    account: str
    ifsc: str
    items: list[Item] = field(default_factory=list)
    status_reason: str | None = None
    email: str | None = None


def _v(code, legal, display, aliases, pan, state, city, address, status, category, terms, bank, acct, ifsc,
       items, reason=None):
    slug = display.lower().split()[0]
    return VendorDef(code, legal, display, aliases, pan, state, city, address, status, category, terms, bank,
                     acct, ifsc, items, reason, f"accounts@{slug}.example")


VENDORS: list[VendorDef] = [
    _v("V-1001", "Vertex Software Solutions Pvt Ltd", "Vertex Software", ["Vertex Software Solutions"],
       "AAFCV2231K", "29", "Bengaluru", "4th Floor, Prestige Tech Park, Outer Ring Road, Bengaluru 560103",
       "APPROVED", "Software & licences", 30, "HDFC Bank", "50200011223344", "HDFC0001234",
       [Item("Vertex PLM Enterprise licence (annual)", "EA", "42000.00", "18", "997331", "VX-PLM-ENT"),
        Item("Implementation support (person-day)", "DAY", "12000.00", "18", "998313", "VX-IMPL-PD"),
        Item("Premium support plan (annual)", "EA", "85000.00", "18", "998316", "VX-SUP-PRM")]),
    _v("V-1002", "Shree Ganesh Steel Traders", "Shree Ganesh Steel", ["Shree Ganesh Steels", "SG Steel Traders"],
       "ABQFS6610D", "27", "Pune", "Gala 7, Lohiyanagar Industrial Estate, Pune 411042",
       "APPROVED", "Raw materials", 45, "Bank of Maharashtra", "60123456789", "MAHB0000456",
       [Item("MS Angle 50x50x6 mm, 6 m length", "EA", "2150.00", "18", "7216", "SG-ANG-50"),
        Item("MS Plate 10 mm, 1250x2500 mm", "EA", "14800.00", "18", "7208", "SG-PLT-10"),
        Item("TMT Bar Fe500D 12 mm", "KG", "68.00", "18", "7214", "SG-TMT-12")]),
    _v("V-1003", "Meridian Office Supplies LLP", "Meridian Office Supplies", ["Meridian Office"],
       "AAWFM4417P", "27", "Mumbai", "112 Kamala Mills Compound, Lower Parel, Mumbai 400013",
       "APPROVED", "Office supplies", 30, "ICICI Bank", "001405501234", "ICIC0000014",
       [Item("A4 copier paper 75 GSM (ream)", "EA", "285.00", "12", "4802", "MO-A4-75"),
        Item("Whiteboard marker, assorted (box of 10)", "BOX", "450.00", "18", "9608", "MO-WBM-10"),
        Item("Ergonomic office chair, mesh back", "EA", "8900.00", "18", "9401", "MO-CHR-ERG"),
        Item("Lever arch file, A4", "EA", "120.00", "18", "4820", "MO-LAF-A4")]),
    _v("V-1004", "Coastal Logistics Pvt Ltd", "Coastal Logistics", ["Coastal Logistics"],
       "AACCC7781Q", "33", "Chennai", "18 Ennore High Road, Tiruvottiyur, Chennai 600019",
       "APPROVED", "Freight & logistics", 15, "Indian Bank", "6012345001", "IDIB000T012",
       [Item("FTL freight Chennai to Pune, 32 ft container", "TRIP", "68000.00", "12", "996511", "CL-FTL-CHN-PNQ"),
        Item("Loading and unloading charges", "TRIP", "4500.00", "18", "996719", "CL-LU")]),
    _v("V-1005", "Precision Bearings India Pvt Ltd", "Precision Bearings", ["PBI Bearings", "Precision Bearings India"],
       "AADCP9032H", "24", "Rajkot", "Survey 214, Aji GIDC, Rajkot, Gujarat 360003",
       "APPROVED", "Mechanical components", 45, "State Bank of India", "38881234567", "SBIN0003121",
       [Item("Deep groove ball bearing 6205-2RS", "EA", "185.00", "18", "8482", "PB-6205-2RS"),
        Item("Tapered roller bearing 32210", "EA", "1240.00", "18", "8482", "PB-32210"),
        Item("Pillow block bearing UCP 208", "EA", "960.00", "18", "8483", "PB-UCP208")]),
    _v("V-1006", "Nimbus Cloud Services Pvt Ltd", "Nimbus Cloud", ["Nimbus Cloud Services"],
       "AAGCN5520R", "36", "Hyderabad", "Level 9, Cyber Towers, HITEC City, Hyderabad 500081",
       "APPROVED", "Cloud infrastructure", 30, "Axis Bank", "917020045678123", "UTIB0000553",
       [Item("Managed Kubernetes cluster, monthly", "MO", "125000.00", "18", "998315", "NC-MK8S"),
        Item("Object storage 50 TB, monthly", "MO", "38000.00", "18", "998315", "NC-OBJ-50")]),
    _v("V-1007", "Orion Facility Management Services Pvt Ltd", "Orion Facility Management", ["Orion FMS"],
       "AABCO3349E", "27", "Pune", "Office 5, Baner Business Bay, Baner, Pune 411045",
       "APPROVED", "Facility services", 30, "Kotak Mahindra Bank", "9912345678", "KKBK0001777",
       [Item("Housekeeping services, monthly (24 staff)", "MO", "384000.00", "18", "998533", "OR-HK-24"),
        Item("Pest control, quarterly", "EA", "18500.00", "18", "998531", "OR-PEST-Q")]),
    _v("V-1008", "Sahyadri Packaging Industries", "Sahyadri Packaging", ["Sahyadri Packaging"],
       "ACMFS1187B", "27", "Nashik", "B-23, Ambad MIDC, Nashik 422010",
       "APPROVED", "Packaging", 30, "Bank of Baroda", "27150200001234", "BARB0AMBADX",
       [Item("Corrugated box 5-ply 600x400x400 mm", "EA", "78.00", "18", "4819", "SP-CB5-600"),
        Item("Edge protector 50 mm x 1 m", "EA", "12.00", "18", "4823", "SP-EP-50")]),
    _v("V-1009", "Brightline Electricals Pvt Ltd", "Brightline Electricals", ["Brightline Electric"],
       "AAECB6674M", "07", "New Delhi", "A-41, Naraina Industrial Area Phase 1, New Delhi 110028",
       "APPROVED", "Electrical", 30, "Punjab National Bank", "0153002100045678", "PUNB0015300",
       [Item("LED high-bay light 150W", "EA", "4250.00", "18", "9405", "BL-HB-150"),
        Item("Armoured cable 4C x 16 sq mm", "M", "520.00", "18", "8544", "BL-AC-4C16"),
        Item("MCB distribution board 12-way", "EA", "6800.00", "18", "8537", "BL-DB-12")]),
    _v("V-1010", "Kaveri Industrial Gases Ltd", "Kaveri Industrial Gases", ["Kaveri Gases"],
       "AABCK8890F", "29", "Bengaluru", "Plot 19, Peenya Industrial Area Phase 2, Bengaluru 560058",
       "APPROVED", "Consumables", 30, "Canara Bank", "0412201005678", "CNRB0000412",
       [Item("Industrial oxygen cylinder 7 cu.m, refill", "EA", "340.00", "12", "2804", "KG-O2-7"),
        Item("Argon cylinder 7 cu.m, refill", "EA", "1150.00", "12", "2804", "KG-AR-7")]),
    _v("V-1011", "TrueNorth Consulting LLP", "TrueNorth Consulting", ["True North Consulting"],
       "AAKFT2290C", "06", "Gurugram", "Tower B, DLF Cyber City Phase 2, Gurugram 122002",
       "APPROVED", "Professional services", 30, "HDFC Bank", "50200099887766", "HDFC0000090",
       [Item("Process improvement advisory (person-day)", "DAY", "45000.00", "18", "998311", "TN-ADV-PD")]),
    _v("V-1012", "Apex Safety Equipment Co", "Apex Safety Equipment", ["Apex Safety"],
       "AAOFA7712G", "24", "Ahmedabad", "21 Naroda GIDC Phase 3, Ahmedabad 382330",
       "PENDING_ONBOARDING", "Safety equipment", 30, "Bank of Baroda", "13450200007890", "BARB0NARODA",
       [Item("Safety helmet with chin strap", "EA", "380.00", "18", "6506", "AS-HLM"),
        Item("Safety shoes, steel toe", "PAIR", "1450.00", "18", "6403", "AS-SHOE")],
       "Onboarding documents (cancelled cheque, MSME certificate) awaited."),
    _v("V-1013", "Redwood Print & Media Pvt Ltd", "Redwood Print & Media", ["Redwood Print"],
       "AACCR4456L", "27", "Mumbai", "7 Sun Mill Compound, Lower Parel, Mumbai 400013",
       "BLOCKED", "Marketing & print", 30, "Yes Bank", "002281300004567", "YESB0000022",
       [Item("Product catalogue print run, 5000 copies", "LOT", "240000.00", "18", "4911", "RW-CAT-5K"),
        Item("Trade-show banner 3 x 2 m", "EA", "6500.00", "18", "4911", "RW-BNR-32")],
       "Blocked 2026-09-18: failed periodic KYC re-verification."),
    _v("V-1014", "Lotus Canteen Services", "Lotus Canteen Services", ["Lotus Canteen"],
       "AJXPL5521H", "27", "Pune", "Shop 3, Nehru Nagar, Pimpri, Pune 411018",
       "APPROVED", "Canteen services", 15, "Saraswat Bank", "610000000123456", "SRCB0000061",
       [Item("Employee meals (per plate)", "EA", "95.00", "5", "996331", "LC-MEAL")]),
    _v("V-1015", "Summit Hydraulics Pvt Ltd", "Summit Hydraulics", ["Summit Hydraulic"],
       "AAICS3378N", "33", "Chennai", "No. 8, SIDCO Industrial Estate, Ambattur, Chennai 600098",
       "APPROVED", "Hydraulics", 45, "Indian Overseas Bank", "100902000012345", "IOBA0001009",
       [Item("Hydraulic cylinder 63 bore x 300 stroke", "EA", "18600.00", "18", "8412", "SH-CYL-63300"),
        Item("Hydraulic hose assembly 1/2 in x 1 m", "EA", "1240.00", "18", "4009", "SH-HOSE-12"),
        Item("Gear pump 16 cc", "EA", "22400.00", "18", "8413", "SH-GP-16")]),
    _v("V-1016", "Indus Fasteners Pvt Ltd", "Indus Fasteners", ["Indus Fasteners"],
       "AADCI6619J", "03", "Ludhiana", "E-112, Focal Point Phase 8, Ludhiana 141010",
       "APPROVED", "Fasteners", 30, "Punjab & Sind Bank", "03681000045671", "PSIB0000368",
       [Item("Hex bolt M12 x 60 HT 8.8, zinc plated", "EA", "14.50", "18", "7318", "IF-HB-M12-60"),
        Item("Hex nut M12 HT, zinc plated", "EA", "4.20", "18", "7318", "IF-HN-M12"),
        Item("Spring washer M12", "EA", "1.10", "18", "7318", "IF-SW-M12")]),
    _v("V-1017", "Indus Fastening Systems Pvt Ltd", "Indus Fastening Systems", ["Indus Fastening"],
       "AADCI7720K", "03", "Ludhiana", "F-27, Focal Point Phase 5, Ludhiana 141010",
       "APPROVED", "Fasteners", 30, "HDFC Bank", "50200077665544", "HDFC0000368",
       [Item("Anchor bolt M16 x 150", "EA", "42.00", "18", "7318", "IFS-AB-M16"),
        Item("Threaded rod M10 x 1 m", "EA", "68.00", "18", "7318", "IFS-TR-M10")]),
    _v("V-1018", "GreenLeaf IT Hardware Pvt Ltd", "GreenLeaf IT Hardware", ["GreenLeaf IT", "Greenleaf Hardware"],
       "AAHCG9981D", "29", "Bengaluru", "22 SP Road, Bengaluru 560002",
       "APPROVED", "IT hardware", 30, "ICICI Bank", "033405007788", "ICIC0000334",
       [Item(desc, unit, price, "18", hsn, code) for desc, unit, price, hsn, code in [
           ("Laptop 14 in, Core i7, 16 GB, 512 GB SSD", "EA", "78500.00", "8471", "GL-LT-14I7"),
           ("Laptop 15 in, Core i5, 16 GB, 512 GB SSD", "EA", "64200.00", "8471", "GL-LT-15I5"),
           ("Docking station USB-C, dual display", "EA", "9800.00", "8471", "GL-DOCK-C"),
           ("Monitor 24 in IPS, FHD", "EA", "11200.00", "8528", "GL-MON-24"),
           ("Monitor 27 in IPS, QHD", "EA", "21400.00", "8528", "GL-MON-27"),
           ("Wireless keyboard and mouse combo", "EA", "2350.00", "8471", "GL-KBM-WL"),
           ("USB-C to HDMI adapter", "EA", "1150.00", "8544", "GL-ADP-HDMI"),
           ("Laptop backpack, 15.6 in", "EA", "1890.00", "4202", "GL-BAG-156"),
           ("Noise-cancelling USB headset", "EA", "4600.00", "8518", "GL-HS-NC"),
           ("Webcam 1080p with privacy shutter", "EA", "3250.00", "8525", "GL-CAM-1080"),
           ("Network switch 24-port gigabit, managed", "EA", "28900.00", "8517", "GL-SW-24"),
           ("Wi-Fi 6 access point, ceiling mount", "EA", "15600.00", "8517", "GL-AP-WF6"),
           ("Cat6 patch cord 2 m", "EA", "180.00", "8544", "GL-C6-2M"),
           ("Cat6 patch cord 5 m", "EA", "290.00", "8544", "GL-C6-5M"),
           ("UPS 1 kVA line interactive", "EA", "8700.00", "8504", "GL-UPS-1K"),
           ("External SSD 1 TB, USB 3.2", "EA", "7400.00", "8471", "GL-SSD-1T"),
           ("Laser printer A4 mono, duplex", "EA", "16800.00", "8443", "GL-PRN-A4"),
           ("Toner cartridge for A4 mono printer", "EA", "4200.00", "8443", "GL-TNR-A4"),
           ("Rack server 1U, 2x Xeon, 64 GB", "EA", "385000.00", "8471", "GL-SRV-1U"),
           ("Server rail kit 1U", "EA", "6400.00", "8473", "GL-RAIL-1U"),
           ("NAS 4-bay with 4x 8 TB drives", "EA", "142000.00", "8471", "GL-NAS-4B"),
           ("KVM switch 8-port", "EA", "12600.00", "8471", "GL-KVM-8"),
           ("Surge protector 6-socket", "EA", "1450.00", "8536", "GL-SURGE-6"),
           ("Cable management tray", "EA", "2100.00", "7326", "GL-TRAY"),
           ("Laptop privacy screen 14 in", "EA", "2650.00", "9001", "GL-PRIV-14"),
           ("Barcode scanner, handheld 2D", "EA", "6900.00", "8471", "GL-BCS-2D"),
       ]]),
]

VENDOR_BY_CODE = {v.code: v for v in VENDORS}


@dataclass
class PODef:
    po_number: str
    vendor_code: str
    po_type: str
    po_date: date
    description: str
    lines: list[tuple[int, str]]  # (item index in vendor catalogue, quantity)
    status: str = "OPEN"
    valid_until: date = date(2027, 3, 31)
    requester: str = "Plant Operations"
    cost_centre: str = "CC-PNQ-OPS"


PURCHASE_ORDERS: list[PODef] = [
    # ---- Scenario POs -------------------------------------------------------------------------------------
    PODef("PO-450101", "V-1005", "GOODS", date(2026, 9, 22), "Bearings for conveyor line refurbishment",
          [(0, "400"), (1, "120"), (2, "60")], requester="Maintenance", cost_centre="CC-PNQ-MNT"),
    PODef("PO-450109", "V-1001", "SERVICES", date(2026, 10, 1), "PLM licences and implementation support",
          [(0, "10"), (1, "5")], requester="Engineering IT", cost_centre="CC-PNQ-ENG"),
    PODef("PO-450103", "V-1003", "GOODS", date(2026, 9, 15), "Office consumables Q3",
          [(0, "200"), (1, "30"), (3, "150")], requester="Administration", cost_centre="CC-PNQ-ADM"),
    PODef("PO-450110", "V-1002", "GOODS", date(2026, 9, 5), "Structural steel for mezzanine floor",
          [(0, "400"), (1, "120")], requester="Projects", cost_centre="CC-PNQ-PRJ"),
    PODef("PO-450120", "V-1016", "GOODS", date(2026, 8, 28), "Fasteners for assembly line 3",
          [(0, "5000"), (1, "5000")], requester="Production", cost_centre="CC-PNQ-PRD"),
    PODef("PO-450130", "V-1004", "SERVICES", date(2026, 10, 3), "Q4 outbound freight, Chennai lanes",
          [(0, "6"), (1, "6")], requester="Logistics", cost_centre="CC-PNQ-LOG"),
    PODef("PO-450131", "V-1004", "SERVICES", date(2026, 10, 6), "Q4 inbound freight, Chennai plant transfers",
          [(0, "5"), (1, "5")], requester="Logistics", cost_centre="CC-PNQ-LOG"),
    PODef("PO-450108", "V-1008", "GOODS", date(2026, 10, 2), "Export packaging, November shipments",
          [(0, "3000"), (1, "6000")], requester="Dispatch", cost_centre="CC-PNQ-DSP"),
    PODef("PO-450106", "V-1006", "SERVICES", date(2026, 4, 1), "Cloud hosting FY 2026-27",
          [(0, "12"), (1, "12")], requester="Corporate IT", cost_centre="CC-PNQ-IT"),
    PODef("PO-450112", "V-1009", "GOODS", date(2026, 9, 18), "Warehouse lighting upgrade",
          [(0, "40"), (1, "500"), (2, "4")], requester="Facilities", cost_centre="CC-PNQ-FAC"),
    PODef("PO-450113", "V-1013", "SERVICES", date(2026, 8, 12), "Product catalogue 2027 print",
          [(0, "1"), (1, "6")], requester="Marketing", cost_centre="CC-PNQ-MKT"),
    PODef("PO-450114", "V-1012", "GOODS", date(2026, 10, 9), "PPE replenishment",
          [(0, "150"), (1, "150")], requester="EHS", cost_centre="CC-PNQ-EHS"),
    PODef("PO-450118", "V-1018", "GOODS", date(2026, 9, 25), "IT hardware refresh, Pune office",
          [(i, q) for i, q in enumerate(["12", "8", "20", "20", "6", "25", "20", "20", "15", "10", "2", "6", "80",
                                         "40", "4", "6", "2", "8", "1", "1", "1", "1", "10", "6", "12", "4"])],
          requester="Corporate IT", cost_centre="CC-PNQ-IT"),
    PODef("PO-450107", "V-1007", "SERVICES", date(2026, 4, 1), "Housekeeping and pest control FY 2026-27",
          [(0, "12"), (1, "4")], requester="Administration", cost_centre="CC-PNQ-ADM"),
    # ---- Background POs (history & reference) --------------------------------------------------------------
    PODef("PO-450115", "V-1010", "GOODS", date(2026, 10, 1), "Welding gases, October",
          [(0, "120"), (1, "40")], requester="Production", cost_centre="CC-PNQ-PRD"),
    PODef("PO-450116", "V-1015", "GOODS", date(2026, 9, 12), "Press hydraulics overhaul",
          [(0, "4"), (1, "24"), (2, "2")], requester="Maintenance", cost_centre="CC-PNQ-MNT"),
    PODef("PO-450117", "V-1015", "GOODS", date(2026, 10, 20), "Spare hydraulic pumps",
          [(2, "3")], requester="Maintenance", cost_centre="CC-PNQ-MNT"),
    PODef("PO-450119", "V-1014", "SERVICES", date(2026, 10, 1), "Canteen services, October",
          [(0, "6200")], requester="HR", cost_centre="CC-PNQ-HR"),
    PODef("PO-450121", "V-1011", "SERVICES", date(2026, 9, 1), "Lean manufacturing advisory",
          [(0, "12")], requester="Operations Excellence", cost_centre="CC-PNQ-OPX"),
    PODef("PO-450122", "V-1017", "GOODS", date(2026, 10, 4), "Anchor bolts for machine foundations",
          [(0, "600"), (1, "200")], requester="Projects", cost_centre="CC-PNQ-PRJ"),
    PODef("PO-450123", "V-1003", "GOODS", date(2026, 10, 14), "Office chairs, new finance bay",
          [(2, "12")], requester="Administration", cost_centre="CC-PNQ-ADM"),
    PODef("PO-450124", "V-1009", "GOODS", date(2026, 7, 2), "Panel room electricals", [(2, "6")],
          status="CLOSED", requester="Facilities", cost_centre="CC-PNQ-FAC"),
    PODef("PO-450125", "V-1005", "GOODS", date(2026, 10, 18), "Spare bearings stock", [(0, "800"), (2, "40")],
          requester="Stores", cost_centre="CC-PNQ-STR"),
    PODef("PO-450126", "V-1002", "GOODS", date(2026, 10, 12), "TMT bars for plinth work", [(2, "6000")],
          requester="Projects", cost_centre="CC-PNQ-PRJ"),
    PODef("PO-450127", "V-1001", "SERVICES", date(2026, 10, 15), "Premium support renewal", [(2, "1")],
          requester="Engineering IT", cost_centre="CC-PNQ-ENG"),
    PODef("PO-450128", "V-1010", "GOODS", date(2026, 11, 1), "Welding gases, November", [(0, "120"), (1, "40")],
          requester="Production", cost_centre="CC-PNQ-PRD"),
    PODef("PO-450129", "V-1016", "GOODS", date(2026, 10, 25), "Fasteners for line 4 tooling",
          [(0, "2000"), (2, "2000")], requester="Production", cost_centre="CC-PNQ-PRD"),
    PODef("PO-450132", "V-1008", "GOODS", date(2026, 6, 10), "Packaging trial lot", [(0, "500")],
          status="CANCELLED", requester="Dispatch", cost_centre="CC-PNQ-DSP"),
    PODef("PO-450133", "V-1014", "SERVICES", date(2026, 11, 1), "Canteen services, November", [(0, "6400")],
          requester="HR", cost_centre="CC-PNQ-HR"),
    PODef("PO-450134", "V-1018", "GOODS", date(2026, 11, 3), "Laptops for graduate hires", [(0, "6"), (2, "6")],
          requester="Corporate IT", cost_centre="CC-PNQ-IT"),
    PODef("PO-450135", "V-1011", "SERVICES", date(2026, 11, 2), "Working-capital diagnostic", [(0, "8")],
          requester="Finance", cost_centre="CC-PNQ-FIN"),
    PODef("PO-450136", "V-1007", "SERVICES", date(2026, 10, 28), "Deep cleaning, annual shutdown", [(1, "2")],
          requester="Administration", cost_centre="CC-PNQ-ADM"),
    PODef("PO-450137", "V-1006", "SERVICES", date(2026, 10, 20), "DR environment, monthly", [(1, "6")],
          requester="Corporate IT", cost_centre="CC-PNQ-IT"),
    PODef("PO-450138", "V-1012", "GOODS", date(2026, 11, 4), "Safety shoes for contractors", [(1, "80")],
          requester="EHS", cost_centre="CC-PNQ-EHS"),
]

PO_BY_NUMBER = {p.po_number: p for p in PURCHASE_ORDERS}


@dataclass
class GRNDef:
    grn_number: str
    po_number: str
    received_date: date
    quantities: dict[int, str]  # PO line number (1-based) -> received qty
    received_by: str = "Stores - Bhosari"
    warehouse: str = "WH-PNQ-01"


GOODS_RECEIPTS: list[GRNDef] = [
    GRNDef("GRN-780101", "PO-450101", date(2026, 10, 24), {1: "400", 2: "120", 3: "60"}),
    GRNDef("GRN-780103", "PO-450103", date(2026, 9, 26), {1: "200", 2: "30", 3: "150"}),
    GRNDef("GRN-780110", "PO-450110", date(2026, 9, 30), {1: "250", 2: "80"}),
    GRNDef("GRN-780111", "PO-450110", date(2026, 10, 21), {1: "150", 2: "40"}),
    GRNDef("GRN-780120", "PO-450120", date(2026, 9, 19), {1: "5000", 2: "5000"}),
    GRNDef("GRN-780108", "PO-450108", date(2026, 11, 3), {1: "3000", 2: "6000"}),
    GRNDef("GRN-780112", "PO-450112", date(2026, 10, 15), {1: "40", 2: "500", 3: "4"}),
    GRNDef("GRN-780118", "PO-450118", date(2026, 10, 22),
           {i + 1: q for i, q in enumerate(["12", "8", "20", "20", "6", "25", "20", "20", "15", "10", "2", "6",
                                            "80", "40", "4", "6", "2", "8", "1", "1", "1", "1", "10", "6", "12",
                                            "4"])}),
    GRNDef("GRN-780115", "PO-450115", date(2026, 10, 10), {1: "120", 2: "40"}),
    GRNDef("GRN-780116", "PO-450116", date(2026, 10, 5), {1: "2", 2: "24", 3: "1"}),
    GRNDef("GRN-780122", "PO-450122", date(2026, 10, 19), {1: "600", 2: "200"}),
    GRNDef("GRN-780123", "PO-450123", date(2026, 10, 29), {1: "12"}),
    GRNDef("GRN-780128", "PO-450128", date(2026, 11, 8), {1: "120", 2: "40"}),
    GRNDef("GRN-780124", "PO-450124", date(2026, 7, 20), {1: "6"}),
    GRNDef("GRN-780114", "PO-450114", date(2026, 10, 27), {1: "150", 2: "150"}),
]

# Vendor master bank details are the "verified" ones above. This is the *different* account printed on the
# bank-detail-change scenario invoice (S08). It is never written into the vendor master.
S08_INVOICE_BANK = {"bank_name": "IndusInd Bank", "account": "259874110032", "ifsc": "INDB0000731"}
