"""
Upload FinOPD data + LoRA weights to HuggingFace Hub (NOT to git).
Reads HF_TOKEN from environment (never hard-coded).

Usage:
  export HF_TOKEN=hf_xxx        # or put in .env and `source`
  python scripts/upload_hf.py --repo RWLinno/FinOPD --what data
  python scripts/upload_hf.py --repo RWLinno/FinOPD --what weights
"""
import os, sys, argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="RWLinno/FinOPD")
    ap.add_argument("--what", choices=["data", "weights", "results"], default="data")
    ap.add_argument("--ckpt", default="outputs/opd_lora_qwen35_v3/v0-20260618-054530/checkpoint-988")
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("ERROR: set HF_TOKEN in the environment (see .env.example).")

    from huggingface_hub import HfApi, create_repo
    api = HfApi(token=token)
    repo_type = "dataset" if args.what in ("data", "results") else "model"
    repo_id = args.repo if "/" in args.repo else f"{args.repo}"
    create_repo(repo_id, token=token, repo_type=repo_type, exist_ok=True, private=False)

    if args.what == "data":
        for f in ["data/processed/us_dow30.csv", "data/processed/cn_csi300.csv"]:
            if Path(f).exists():
                api.upload_file(path_or_fileobj=f, path_in_repo=f"processed/{Path(f).name}",
                                repo_id=repo_id, repo_type=repo_type)
                print("uploaded", f)
    elif args.what == "results":
        snap = Path("KDD27_FinOPD_overleaf/data_snapshots")
        for f in snap.glob("*.json"):
            api.upload_file(path_or_fileobj=str(f), path_in_repo=f"results/{f.name}",
                            repo_id=repo_id, repo_type=repo_type)
            print("uploaded", f.name)
    else:  # weights
        ck = Path(args.ckpt)
        if not ck.exists():
            sys.exit(f"checkpoint not found: {ck}")
        api.upload_folder(folder_path=str(ck), path_in_repo="lora/checkpoint-988",
                          repo_id=repo_id, repo_type=repo_type,
                          ignore_patterns=["*optim_states.pt", "global_step*/*", "README.md",
                                           "*.pth", "rng_state*", "scheduler.pt", "trainer_state.json"])
        print("uploaded LoRA adapter from", ck)
    print(f"Done -> https://huggingface.co/{'datasets/' if repo_type=='dataset' else ''}{repo_id}")


if __name__ == "__main__":
    main()
