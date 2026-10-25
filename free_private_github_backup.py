"""Free private Git backup for already RSA/AES-GCM encrypted RASD owner evidence.

Manual owner-device tool. NEVER encrypts plaintext or handles a private key.
Pushes only a strictly validated Gate43 ciphertext envelope into a DEDICATED
branch of the EXISTING private RASD-Pilot repository; then independently
re-clones and verifies the exact bytes. Not a remote decryption proof.
No R2 subscription, GitHub Actions/SMTP, shared ledger or hosted secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from gate71_owner_ciphertext_backup_no_network import (
    MAX_ENVELOPE_BYTES, check_owner_ciphertext, prepare_private_ciphertext_backup,
)

PRIVATE_REPO_URL = "https://github.com/Hatem1984/RASD-Pilot.git"
BACKUP_BRANCH = "rasd-owner-ciphertext-backup"
_MAX_GIT_WAIT = 90


def _git(args: list[str], *, cwd: Path, timeout: int = _MAX_GIT_WAIT) -> bytes:
    """Git only via argument vector; never log a credential or raw git output."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never",
               GIT_ASKPASS="")
    try:
        p = subprocess.run(
            ["git", *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("private_ciphertext_git_command_unavailable") from None
    if p.returncode != 0:
        raise RuntimeError("private_ciphertext_git_operation_failed") from None
    return p.stdout


def plan_local_encrypted_backup(source: Path, day: date) -> tuple[bytes, dict]:
    """Check only already encrypted source bytes; never load owner key/Word."""
    source = Path(source)
    if (not source.is_file() or source.is_symlink() or
            source.suffix.lower() != ".json" or
            not 256 <= source.stat().st_size <= MAX_ENVELOPE_BYTES):
        raise ValueError("private_ciphertext_source_not_safe")
    payload = source.read_bytes()
    plan = prepare_private_ciphertext_backup(payload, day=day)
    return payload, plan


def _readback(repo_url: str, expected_path: str, original: bytes,
              sandbox: Path) -> None:
    cloned = sandbox / "independent-readback"
    _git(["clone", "--quiet", "--depth", "1", "--single-branch",
          "--branch", BACKUP_BRANCH, repo_url, str(cloned)], cwd=sandbox)
    copy = cloned / expected_path
    if not copy.is_file() or copy.is_symlink():
        raise RuntimeError("remote_private_ciphertext_object_missing")
    actual = copy.read_bytes()
    check_owner_ciphertext(actual)
    if len(actual) != len(original) or actual != original or (
            hashlib.sha256(actual).digest() != hashlib.sha256(original).digest()):
        raise RuntimeError("remote_private_ciphertext_readback_mismatch")


def backup_private_ciphertext(source: Path, *, day: date,
                              repository_url: str = PRIVATE_REPO_URL) -> dict:
    """Upload encrypted bytes only, in immutable digest-addressed Git path.

    repository_url exists solely for offline tests with a local bare Git
    repository. Actual CLI is hardcoded to the approved private GitHub repo.
    """
    if not (repository_url == PRIVATE_REPO_URL or
            repository_url.startswith("file://")):
        raise ValueError("private_ciphertext_unapproved_destination")
    payload, plan = plan_local_encrypted_backup(source, day)
    relative = plan["object_key"]
    with tempfile.TemporaryDirectory(prefix="rasd-private-ciphertext-") as tmp:
        sandbox = Path(tmp)
        cloned = sandbox / "isolated-push"
        # Git read is needed ONLY to establish whether the dedicated branch
        # already exists. On an empty private backup branch, initialize locally.
        try:
            _git(["clone", "--quiet", "--depth", "1", "--single-branch",
                  "--branch", BACKUP_BRANCH, repository_url, str(cloned)],
                 cwd=sandbox)
            existing_branch = True
        except RuntimeError:
            # Do not treat authentication errors as proof of absent branch.
            _git(["ls-remote", "--exit-code", "--heads", repository_url, "main"],
                 cwd=sandbox)
            # A failed clone could be auth/network or the branch being absent.
            # Existence is checked with a second direct ls-remote below.
            _git(["init", "--quiet", str(cloned)], cwd=sandbox)
            _git(["remote", "add", "origin", repository_url], cwd=cloned)
            _git(["checkout", "--quiet", "--orphan", BACKUP_BRANCH], cwd=cloned)
            existing_branch = False
        _git(["config", "user.name", "RASD Private Ciphertext Backup"], cwd=cloned)
        _git(["config", "user.email", "rasd-ciphertext@users.noreply.github.com"],
             cwd=cloned)
        output = cloned / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            if output.is_symlink() or output.read_bytes() != payload:
                raise RuntimeError("private_ciphertext_immutable_key_collision")
            already_present = True
        else:
            output.write_bytes(payload)
            already_present = False
            _git(["add", "--", relative], cwd=cloned)
            staged = _git(["diff", "--cached", "--name-only"], cwd=cloned)
            if staged.strip().decode("utf-8", "replace") != relative:
                raise RuntimeError("private_ciphertext_staged_scope_invalid")
            _git(["commit", "--quiet", "-m",
                  "backup: owner-only ciphertext " + day.isoformat()],
                 cwd=cloned)
            _git(["push", "--quiet", "origin",
                  "HEAD:refs/heads/" + BACKUP_BRANCH], cwd=cloned)
        _readback(repository_url, relative, payload, sandbox)
    return {
        "status": "PRIVATE_GIT_ENCRYPTED_CIPHERTEXT_READBACK_VERIFIED",
        "repository": "Hatem1984/RASD-Pilot" if repository_url == PRIVATE_REPO_URL else "LOCAL_TEST",
        "branch": BACKUP_BRANCH,
        "cairo_day": day.isoformat(),
        "object_key": relative,
        "bytes_verified": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "already_present": already_present,
        "original_owner_ciphertext_used": repository_url == PRIVATE_REPO_URL,
        "original_owner_plaintext_uploaded": False,
        "owner_private_key_accessed": False,
        "remote_byte_identical": True,
        "private_key_decryption_verified": False,
        "human_visual_review": False,
        "email_sent": False,
        "r2_enabled": False,
        "new_paid_subscription": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--day", required=True, type=date.fromisoformat)
    p.add_argument("--ciphertext", required=True, type=Path)
    p.add_argument("--push-private-github", action="store_true")
    args = p.parse_args()
    try:
        if args.push_private_github:
            result = backup_private_ciphertext(args.ciphertext, day=args.day)
        else:
            _, plan = plan_local_encrypted_backup(args.ciphertext, args.day)
            result = {
                "status": "PRIVATE_GITHUB_CIPHERTEXT_PREFLIGHT_ONLY",
                "object_key": plan["object_key"], "envelope_bytes": plan["envelope_bytes"],
                "encrypted_payload_sha256": plan["encrypted_payload_sha256"],
                "uploaded": False, "email_sent": False,
                "new_paid_subscription": False,
            }
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print(json.dumps({"status": "HOLD",
                          "reason": "private_github_encrypted_backup_unverified",
                          "uploaded_verified": False, "email_sent": False,
                          "new_paid_subscription": False}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
