"""지정된 파이썬 환경에서 로컬 게임과 백업을 실행한다."""
import argparse
import json
import os
import secrets
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="신수 로컬 서버와 백업")
    parser.add_argument("command", choices=["run","backup","export-save","import-save","cloud-backup","cloud-import","change-species"])
    parser.add_argument("--output")
    parser.add_argument("--input")
    parser.add_argument("--account", choices=["player1","player2"])
    parser.add_argument("--legacy-id")
    parser.add_argument("--species")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.command in ("export-save","import-save","cloud-backup","cloud-import","change-species"):
        from shisu.infrastructure.database import Database
        from shisu.infrastructure.transfer import import_save, cloud_backup, cloud_download
        database = Database(os.getenv("SHISU_DB_PATH", str(root / "data/shinsu.sqlite3")))
        try:
            if args.command == "change-species":
                if not args.account or not args.species:
                    parser.error("--account와 --species를 모두 지정하세요.")
                backup = database.path.with_name(f"{database.path.stem}-before-species-{args.account}-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3")
                database.backup(backup)
                message = database.change_species(args.account, args.species)
                print(f"안전 백업: {backup}")
                print(message)
            elif args.command == "cloud-backup":
                cloud_backup(database)
            else:
                if not args.account:
                    parser.error("--account로 대상 계정을 지정하세요.")
                if args.command == "export-save":
                    if not args.output:
                        parser.error("--output 경로가 필요합니다.")
                    with Path(args.output).open("x", encoding="utf-8") as handle:
                        json.dump(database.get(args.account), handle, ensure_ascii=False, indent=2)
                else:
                    if args.command == "cloud-import":
                        raw = cloud_download(args.account, args.legacy_id)
                    else:
                        if not args.input:
                            parser.error("--input 경로가 필요합니다.")
                        raw = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
                    backup = import_save(database,args.account,raw,args.replace)
                    print(f"이전 저장 백업: {backup}")
            print("세이브 작업을 완료했습니다.")
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        return
    if args.command == "backup":
        from shisu.infrastructure.database import Database
        source = Path(os.getenv("SHISU_DB_PATH",str(root / "data/shinsu.sqlite3")))
        if not args.output or not source.exists():
            parser.error("존재하는 데이터베이스와 --output 백업 경로가 필요합니다.")
        target = Path(args.output)
        if target.exists():
            parser.error("기존 파일은 덮어쓰지 않습니다. 새 백업 경로를 지정하세요.")
        Database(source).backup(target)
        print("백업을 완료했습니다.")
        return
    if not os.getenv("SHISU_ACCOUNTS"):
        config = root / ".local/accounts.json"
        if not config.exists():
            config.parent.mkdir(parents=True,exist_ok=True)
            data = {f"player{i}":{"name":f"테이머 {i}","code":secrets.token_urlsafe(32)} for i in (1,2)}
            with config.open("x",encoding="utf-8") as file:
                json.dump(data,file,ensure_ascii=False,indent=2)
        os.environ["SHISU_ACCOUNTS"] = config.read_text(encoding="utf-8")
        print(f"각 계정의 접속 코드는 {config}에서 확인하세요. 파일을 공개하지 마세요.")
    os.environ["SHISU_COOKIE_SECURE"] = "false"
    import uvicorn
    uvicorn.run("shisu.api.main:app",host="127.0.0.1",port=8000,workers=1)


if __name__ == "__main__":
    main()
