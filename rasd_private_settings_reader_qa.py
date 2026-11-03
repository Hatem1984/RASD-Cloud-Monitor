"""QA-only cloud settings reader proposal for a pre-approved PRIVATE GitHub repo.

Read-only API with a server-side token. No write, no dispatch, no SMTP. Never
point this at RASD's public code repository or expose the token to owner HTML.
"""
import base64
import json
import re
from urllib.request import Request, urlopen
from rasd_settings_bridge_qa import verify_cloud_ready_manifest

PUBLIC_CODE_REPO="Hatem1984/RASD-Cloud-Monitor"
MAX_MANIFEST_BYTES=60_000

def private_active_config(*, repository, path, ref, token, baseline,
                          api_get=None):
    if (not isinstance(repository,str) or
        not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}",repository) or
        repository.casefold()==PUBLIC_CODE_REPO.casefold()):
        raise RuntimeError("private_config_repository_not_approved")
    if (not isinstance(path,str) or
        not re.fullmatch(r"[A-Za-z0-9/_-]{3,160}\.json",path) or
        path.startswith("/") or ".." in path or
        not isinstance(ref,str) or not re.fullmatch(r"[A-Za-z0-9/_-]{1,80}",ref)):
        raise RuntimeError("private_config_path_invalid")
    if not isinstance(token,str) or len(token)<35:
        raise RuntimeError("private_config_read_secret_missing_hold")
    def fetch(url):
        req=Request(url,headers={"Authorization":"Bearer "+token,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"RASD-private-settings-readonly/1"})
        with urlopen(req,timeout=12) as res:
            b=res.read(MAX_MANIFEST_BYTES+1)
        if len(b)>MAX_MANIFEST_BYTES:raise RuntimeError("private_response_too_large")
        return json.loads(b.decode("utf-8"))
    fetcher=api_get or fetch
    base="https://api.github.com/repos/"+repository
    info=fetcher(base)
    if not isinstance(info,dict) or info.get("private") is not True or info.get("full_name","").casefold()!=repository.casefold():
        raise RuntimeError("private_config_repository_visibility_hold")
    record=fetcher(base+"/contents/"+path+"?ref="+ref)
    if (not isinstance(record,dict) or record.get("type")!="file" or
        record.get("encoding")!="base64" or
        not isinstance(record.get("content"),str) or
        record.get("size",MAX_MANIFEST_BYTES+1)>MAX_MANIFEST_BYTES):
        raise RuntimeError("private_config_file_contract_hold")
    try:
        raw=base64.b64decode(record["content"],validate=False)
        if len(raw)>MAX_MANIFEST_BYTES:raise ValueError("manifest too large")
        manifest=json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeError,TypeError):
        raise RuntimeError("private_config_data_invalid") from None
    return verify_cloud_ready_manifest(manifest,baseline)
