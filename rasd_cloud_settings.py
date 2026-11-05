"""Fail-closed opt-in loader for RASD's existing PRIVATE GitHub repository.

This is never browser JavaScript and never logs the GitHub token or payload.
Default is the original production source configuration. A private approved
manifest and an explicit feature gate are BOTH required to switch sources.
"""
from __future__ import annotations

import os
from rasd_private_settings_reader_qa import private_active_config
from rasd_settings_bridge_qa import scanned_config

REPO = "Hatem1984/RASD-Pilot"  # Current private delivery repository, separate from public code.
BRANCH = "rasd-private-delivery-state"
ACTIVE_PATH = "settings/rasd-owner-active.json"

def load_owner_active_config(baseline, *, environ=None, api_get=None):
    env = os.environ if environ is None else environ
    if env.get("RASD_OWNER_SETTINGS_ENABLED") != "true":
        return baseline, None
    token = env.get("RASD_PRIVATE_LEDGER_TOKEN", "")
    manifest = private_active_config(repository=REPO,path=ACTIVE_PATH,ref=BRANCH,
                                     token=token,baseline=baseline,api_get=api_get)
    # Do not ever accept QA_PREVIEW_NO_SEND as production active.
    if manifest["scope"] != "ACTIVE_APPROVED":
        raise RuntimeError("owner_config_not_production_approved")
    effective = scanned_config(manifest, baseline)
    return effective, manifest
