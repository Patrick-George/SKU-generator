import json
import os

DATA_FILE = "/data/sku_data.json"

def _insert_after(mapping, after_key, new_key, value):
    """Return a new dict with new_key placed immediately after after_key."""
    rebuilt = {}
    inserted = False
    for key, item in mapping.items():
        rebuilt[key] = item
        if key == after_key:
            rebuilt[new_key] = value
            inserted = True
    if not inserted:
        rebuilt[new_key] = value
    return rebuilt


def _copied_options(field):
    """Copy dropdown options, dropping machine-visibility tags."""
    if isinstance(field, list):
        raw = field
    elif isinstance(field, dict):
        raw = field.get("options") or []
    else:
        return []

    options = []
    for opt in raw:
        if not isinstance(opt, dict) or opt.get("type") == "text":
            continue
        code = str(opt.get("code") or "").strip()
        if not code:
            continue
        options.append({
            "code": code,
            "name": opt.get("name", ""),
            "tally_name": opt.get("tally_name", ""),
            "description": opt.get("description", ""),
            "order": opt.get("order", len(options) + 1),
        })
    return options


def _package_contents(length, extras=()):
    """Selector note for one blast package. Shown under the dropdown only."""
    lines = [
        "Blast Machine (incl. Screen + Cover)",
        "Remote Control Valve",
        "Moisture Separator",
        "Abrasive Metering Valve",
        "Threaded Pot Coupling",
        "Four-Jaw Inlet Coupling",
        "Dead Man Handle",
        f"Twin Hose ({length}) + Fittings",
        f'Blast Hose 1-1/4" ({length})',
        "Blast Hose Coupling",
        "Nozzle Holder Nylon (NHP2)",
        "Nozzle #5 (8 mm) / #6 (9.5 mm)",
        "Whip Check",
        "R Clip (only for cast iron hose coupling)",
        *extras,
    ]
    return "\n".join(lines)


_PPE = ("+ Blast Gloves", "+ Blast Suit", "+ Blast Helmet")

# Short ids stay 2A/2B/… The SKU segment and item-name tally are PK + that id.
PACKAGE_SHORT_CODES = ("2A", "2B", "3A", "3B", "4A", "4B")

# Selector notes for Blast Machine Packages. Not copied into the item name or description.
PACKAGE_DETAILS = {
    "2A": _package_contents("20m"),
    "2B": _package_contents("40m"),
    "3A": _package_contents("20m", _PPE),
    "3B": _package_contents("40m", _PPE),
    "4A": _package_contents("20m", (
        "Blast Gloves",
        "Blast Suit",
        "Blast Helmet",
        "+ Breathing Air Filter Single BL 20",
        '+ Breathing Hose 3/8" (20m) + Fittings',
    )),
    "4B": _package_contents("40m", (
        "Blast Gloves",
        "Blast Suit",
        "Blast Helmet",
        "+ Breathing Air Filter Single BL 20",
        '+ Breathing Hose 3/8" (40m) + Fittings',
    )),
}


def _build_blast_machine_packages(blast_machine):
    """Category with capacity and certification copied from Blast Machine when present."""
    source_fields = {}
    if isinstance(blast_machine, dict):
        source_fields = blast_machine.get("fields") or {}

    return {
        "fields": {
            "Capacity": {"order": 1, "options": _copied_options(source_fields.get("Capacity"))},
            "Certification": {"order": 2, "options": _copied_options(source_fields.get("Certification"))},
            "Helmet": {
                "order": 3,
                "options": [
                    {
                        "code": "AS",
                        "name": "Astro",
                        "tally_name": "AS",
                        "description": "Astro Helmet",
                        "order": 1,
                    },
                    {
                        "code": "T6",
                        "name": "Testa",
                        "tally_name": "T6",
                        "description": "Testa Helmet",
                        "order": 2,
                    },
                ],
            },
            "Package": {
                "order": 4,
                "options": [
                    {
                        "code": f"PK{short}",
                        "name": f"Package {short}",
                        "tally_name": f"PK{short}",
                        "description": f"Package {short}",
                        "order": index,
                        "contents": PACKAGE_DETAILS.get(short, ""),
                    }
                    for index, short in enumerate(PACKAGE_SHORT_CODES, start=1)
                ],
            },
        },
        "extras": [],
        "settings": {
            "separator": "",
            "extras_mode": "Multiple",
            "use_short_codes": False,
        },
    }


class GithubStorage:
    """
    Disk-backed persistent storage.
    Class name preserved so the rest of the application remains unchanged.
    """

    def __init__(self):
        self.path = DATA_FILE
        self.can_connect = True

    def load(self):
        """
        Load configuration data from disk.
        If no data file exists yet, seed from bundled data.json (if present).
        """
        data = None
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if data is None:
            seed_path = os.path.join(os.path.dirname(__file__), "data.json")
            if os.path.exists(seed_path):
                try:
                    with open(seed_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    os.makedirs(os.path.dirname(self.path), exist_ok=True)
                    with open(self.path, "w", encoding="utf-8") as out_f:
                        json.dump(data, out_f, indent=2)
                except Exception:
                    data = None

        if data is None:
            data = {"inventory": {}}

        data.setdefault("inventory", {})
        data.setdefault("sku_history", [])
        # Registry of permanently allocated short codes.
        #   short_codes:   signature -> record ({code, prefix, seq, sku, ...})
        #   code_counters: prefix    -> last allocated sequence number
        data.setdefault("short_codes", {})
        data.setdefault("code_counters", {})

        # One-time style migration: BL-3 -> BL-003 (min 3 digits; 1000+ unpadded).
        if self._pad_short_codes_inplace(data):
            try:
                self.save(data)
            except Exception:
                pass

        # One-time seed: Blast Machine Packages. The flag stays set after the
        # first run, including when an admin later deletes the category.
        if self._ensure_blast_machine_packages(data):
            try:
                self.save(data)
            except Exception:
                pass

        # One-time fill of package selector notes. Later edits in admin are kept.
        if self._ensure_package_details(data):
            try:
                self.save(data)
            except Exception:
                pass

        if self._ensure_package_details_v2(data):
            try:
                self.save(data)
            except Exception:
                pass

        if self._ensure_package_pk_codes(data):
            try:
                self.save(data)
            except Exception:
                pass

        return data

    @staticmethod
    def _pad_short_codes_inplace(data):
        """Rewrite unpadded short codes to PREFIX-NNN. Returns True if anything changed."""
        changed = False
        short_codes = data.get("short_codes") or {}
        history = data.get("sku_history") or []
        old_to_new = {}

        for rec in short_codes.values():
            if not isinstance(rec, dict):
                continue
            prefix = rec.get("prefix")
            seq = rec.get("seq")
            if prefix is None or seq is None:
                code = str(rec.get("code") or "")
                if "-" in code:
                    prefix, _, num = code.rpartition("-")
                    if num.isdigit():
                        seq = int(num)
                        rec.setdefault("prefix", prefix)
                        rec.setdefault("seq", seq)
            if prefix is None or seq is None:
                continue
            try:
                new_code = f"{str(prefix).upper()}-{int(seq):03d}"
            except (TypeError, ValueError):
                continue
            old_code = rec.get("code")
            if old_code != new_code:
                if old_code:
                    old_to_new[str(old_code)] = new_code
                rec["code"] = new_code
                rec["prefix"] = str(prefix).upper()
                changed = True

        if old_to_new:
            for entry in history:
                if not isinstance(entry, dict):
                    continue
                sc = entry.get("short_code")
                if sc in old_to_new:
                    entry["short_code"] = old_to_new[sc]
                    changed = True

        return changed

    @staticmethod
    def _ensure_blast_machine_packages(data):
        """Insert Blast Machine Packages once. Returns True if data changed."""
        if data.get("blast_machine_packages_seeded"):
            return False

        inventory = data.setdefault("inventory", {})
        if not isinstance(inventory, dict):
            data["blast_machine_packages_seeded"] = True
            return True

        if "Blast Machine Packages" not in inventory:
            category = _build_blast_machine_packages(inventory.get("Blast Machine"))
            data["inventory"] = _insert_after(
                inventory, "Blast Machine", "Blast Machine Packages", category
            )

        data["blast_machine_packages_seeded"] = True
        return True

    @staticmethod
    def _ensure_package_details(data):
        """Fill empty 3A/3B selector notes once. Returns True if data changed."""
        if data.get("package_details_seeded"):
            return False

        inventory = data.get("inventory") or {}
        category = inventory.get("Blast Machine Packages") if isinstance(inventory, dict) else None
        if isinstance(category, dict):
            options = ((category.get("fields") or {}).get("Package") or {}).get("options") or []
            for opt in options:
                if not isinstance(opt, dict):
                    continue
                code = str(opt.get("code") or "").strip()
                short = code[2:] if code.startswith("PK") else code
                if short in PACKAGE_DETAILS and not str(opt.get("contents") or "").strip():
                    opt["contents"] = PACKAGE_DETAILS[short]

        data["package_details_seeded"] = True
        return True

    @staticmethod
    def _ensure_package_details_v2(data):
        """Fill 2A/2B notes and add 4A/4B once. Returns True if data changed."""
        if data.get("package_details_v2_seeded"):
            return False

        inventory = data.get("inventory") or {}
        category = inventory.get("Blast Machine Packages") if isinstance(inventory, dict) else None
        if isinstance(category, dict):
            package = (category.get("fields") or {}).get("Package")
            if isinstance(package, dict):
                options = package.setdefault("options", [])
                by_code = {
                    str(opt.get("code") or "").strip(): opt
                    for opt in options
                    if isinstance(opt, dict)
                }
                next_order = 1 + max(
                    (int(opt.get("order") or 0) for opt in options if isinstance(opt, dict)),
                    default=0,
                )
                for short in PACKAGE_SHORT_CODES:
                    text = PACKAGE_DETAILS.get(short, "")
                    sku_code = f"PK{short}"
                    opt = by_code.get(sku_code) or by_code.get(short)
                    if opt is None:
                        options.append({
                            "code": sku_code,
                            "name": f"Package {short}",
                            "tally_name": sku_code,
                            "description": f"Package {short}",
                            "order": next_order,
                            "contents": text,
                        })
                        next_order += 1
                    elif text and not str(opt.get("contents") or "").strip():
                        opt["contents"] = text

        data["package_details_v2_seeded"] = True
        return True

    @staticmethod
    def _ensure_package_pk_codes(data):
        """Rename package codes 2A -> PK2A and match the item-name tally. Once."""
        if data.get("package_pk_codes_seeded"):
            return False

        inventory = data.get("inventory") or {}
        category = inventory.get("Blast Machine Packages") if isinstance(inventory, dict) else None
        if isinstance(category, dict):
            package = (category.get("fields") or {}).get("Package")
            if isinstance(package, dict):
                options = package.get("options") or []
                by_code = {
                    str(opt.get("code") or "").strip(): opt
                    for opt in options
                    if isinstance(opt, dict)
                }
                for short in PACKAGE_SHORT_CODES:
                    new_code = f"PK{short}"
                    short_opt = by_code.get(short)
                    pk_opt = by_code.get(new_code)
                    target = pk_opt
                    if short_opt is not None and pk_opt is None:
                        short_opt["code"] = new_code
                        by_code[new_code] = short_opt
                        target = short_opt
                    elif short_opt is not None:
                        target = short_opt if pk_opt is None else pk_opt
                    if target is None:
                        continue
                    tally = str(target.get("tally_name") or "").strip()
                    if tally in ("", short, new_code):
                        target["tally_name"] = new_code

        data["package_pk_codes_seeded"] = True
        return True

    def save(self, data):
        """Save configuration data to disk."""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def save_history(self, history):
        """
        Persist just the sku_history list without touching inventory.
        Read-modify-write so concurrent admin edits aren't clobbered.
        """
        try:
            current = self.load()
            current["sku_history"] = history
            return self.save(current)
        except Exception:
            return False

    def save_registry(self, short_codes, code_counters):
        """
        Persist just the short-code registry without touching inventory or
        history. Read-modify-write so concurrent edits aren't clobbered.
        """
        try:
            current = self.load()
            current["short_codes"] = short_codes
            current["code_counters"] = code_counters
            return self.save(current)
        except Exception:
            return False
