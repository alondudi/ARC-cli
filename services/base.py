# services/base.py
import boto3
import json
import os
from pathlib import Path


class BaseService:
    ARC_HOME = Path.home() / ".arc"
    KEYS_DIR = ARC_HOME / "keys"
    CONFIG_PATH = KEYS_DIR / "config.json"

    def __init__(self):
        self.ARC_HOME.mkdir(exist_ok=True)
        self.KEYS_DIR.mkdir(exist_ok=True)

        config = self._load_config()
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.region = config.get("region", "us-east-1")

        try:
            self.session = boto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            self.sts = self.session.client('sts')
        except Exception as e:
            print(f"Connection Error: {e}")

    def _load_config(self):
        """Loading configuration from keys file"""
        if self.CONFIG_PATH.exists():
            try:
                return json.loads(self.CONFIG_PATH.read_text())
            except:
                return {}
        return {}

    def save_config(self, access_key, secret_key, region):
        """Save configuration to keys file"""
        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region
        }
        self.CONFIG_PATH.write_text(json.dumps(data, indent=4))
        self.session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.sts = self.session.client('sts')

    def validate_connection(self):
        """Connection check AWS"""
        try:
            identity = self.sts.get_caller_identity()
            return True, identity.get('Arn')
        except Exception as e:
            return False, str(e)