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
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"inventory": {}}

        seed_path = os.path.join(os.path.dirname(__file__), "data.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w", encoding="utf-8") as out_f:
                    json.dump(data, out_f, indent=2)
                return data
            except Exception:
                return {"inventory": {}}

        return {"inventory": {}}

    def save(self, data):
        """Save configuration data to disk."""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
