import json
import os

DATA_FILE = "/data/sku_data.json"


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
