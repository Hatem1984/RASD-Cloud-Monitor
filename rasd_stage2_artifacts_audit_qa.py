"""RASD QA private Actions artifacts audit. Read-only, NO SEND.

One immutable artifact per real GitHub scheduled run. Missing/delayed run is
reported missing; a probe or synthetic test never counts toward 44 slots.
This auditor never changes GitHub files or the delivery ledger.
"""
from __future__ import annotations
import argparse,io,json,os,zipfile
from datetime import datetime,date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from rasd_stage2_observer_qa import audit_records,load_config
from rasd_stage2_provenance_qa import validate_scheduled_artifact
REPO="Hatem1984/RASD-Pilot"
BASE="https://api.github.com/repos/"+REPO
MAX_ZIP=256000
MAX_RECORDS=400

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def _get(path,token):
    req=Request(BASE+path,headers={"Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json","User-Agent":"RASD-QA-artifact-auditor"})
    if not path.endswith("/zip"):
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            return response.read(800000)
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            data=response.read(MAX_ZIP+1)
    except HTTPError as error:
        if error.code not in (302,307):raise
        location=error.headers.get("Location","")
        host=urlsplit(location)
        if (host.scheme!="https" or not host.hostname or
            not (host.hostname.endswith(".actions.githubusercontent.com")
                 or host.hostname.endswith(".blob.core.windows.net")
                 or host.hostname=="objects.githubusercontent.com")):
            raise RuntimeError("qa_artifact_cdn_untrusted")
        # Signed download URL is requested WITHOUT forwarding the GitHub token.
        with urlopen(Request(location,headers={"User-Agent":"RASD-QA-artifact-readonly"}),
                     timeout=20) as response:
            data=response.read(MAX_ZIP+1)
    if len(data)>MAX_ZIP:raise ValueError("artifact_zip_oversize")
    return data

def read_private_artifacts(token,target_day):
    if not isinstance(token,str) or len(token)<16:
        raise RuntimeError("qa_actions_read_token_unavailable")
    out=[]
    for page in range(1,6):
        body=json.loads(_get("/actions/artifacts?name=rasd-stage2-observation&per_page=100&page="+str(page),token))
        records=body.get("artifacts",[])
        for row in records:
            if (not isinstance(row.get("created_at"),str) or
                row["created_at"][:10] not in
                (target_day.isoformat(),(target_day-__import__("datetime").timedelta(days=1)).isoformat())):
                continue
            if (row.get("name")!="rasd-stage2-observation"
                or row.get("expired") is not False
                or not isinstance(row.get("id"),int)
                or (row.get("size_in_bytes") or MAX_ZIP+1)>MAX_ZIP
                or not isinstance(row.get("workflow_run"),dict)
                or row["workflow_run"].get("head_branch")!="main"):
                continue
            zipbytes=_get("/actions/artifacts/"+str(row["id"])+"/zip",token)
            with zipfile.ZipFile(io.BytesIO(zipbytes)) as archive:
                if archive.namelist()!=["observation.json"]:
                    raise RuntimeError("qa_immutable_artifact_contract_hold")
                if archive.getinfo("observation.json").file_size>MAX_ZIP:
                    raise RuntimeError("qa_artifact_json_oversize")
                receipt=json.loads(archive.read("observation.json").decode("utf-8"))
            if str(receipt.get("github_run_id"))!=str(row["workflow_run"].get("id")):
                raise RuntimeError("qa_artifact_run_identity_hold")
            # Independently verify REAL scheduled-run provenance from GitHub's
            # run metadata. A manual smoke or fabricated ZIP cannot cover a
            # halfhour slot, regardless of JSON fields inside the receipt.
            run=json.loads(_get("/actions/runs/"+str(row["workflow_run"]["id"]),token))
            try:
                validate_scheduled_artifact(receipt,row,run)
            except (ValueError,TypeError,KeyError):
                raise RuntimeError("qa_scheduled_run_provenance_hold") from None
            out.append(receipt)
            if len(out)>MAX_RECORDS:raise RuntimeError("qa_artifacts_over_limit")
        if len(records)<100:
            break
    else:
        raise RuntimeError("qa_artifact_pagination_incomplete_hold")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--baseline",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--mode",choices=("offline","github"),required=True)
    p.add_argument("--receipts-dir",default=".")
    args=p.parse_args()
    day=date.fromisoformat(args.day)
    config,manifest=load_config(args.manifest,args.baseline)
    if args.mode=="github":
        if (os.environ.get("GITHUB_REPOSITORY")!=REPO or
            os.environ.get("GITHUB_REF")!="refs/heads/main"):
            raise RuntimeError("qa_audit_repo_not_authorized")
        records=read_private_artifacts(os.environ.get("GITHUB_TOKEN",""),day)
    else:
        records=[json.loads(p.read_text(encoding="utf-8"))
                 for p in Path(args.receipts_dir).glob("*.json")]
    # Ignore other dates in listing. Audit refuses fake date/clock in
    # records that claim this day; wrong-day records never count.
    selected=[r for r in records if isinstance(r,dict) and
              r.get("day_cairo")==day.isoformat()]
    report=audit_records(selected,day,
       [f["id"] for f in config["feeds"]],manifest["active_version"],
       expected_code_sha=os.environ.get("RASD_QA_PUBLIC_COMMIT","4d0217a2b1c0b15e3949c3e075fae31b9cb3e896"),
       expected_config_sha256=manifest["sha256"])
    report["receipt_count"]=len(selected)
    report["config_sha256"]=manifest["sha256"]
    report["source"]="PRIVATE_ACTIONS_IMMUTABLE_ARTIFACTS" if args.mode=="github" else "OFFLINE_TEST_ONLY"
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:report[k] for k in ("day_cairo","status","expected_slots",
      "observed_slots","healthy_slots","rejected_records","receipt_count","smtp_sent")}
    print("RASD_QA_DAY_AUDIT="+json.dumps(summary,sort_keys=True),flush=True)
    print("RASD_QA_NO_SMTP=true",flush=True)
    if args.mode=="github" and not report["complete"]:
        print("::warning::RASD 44-slot evidence is INCOMPLETE; do not approve daily report",flush=True)

if __name__=="__main__":main()
