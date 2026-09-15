"""지정된 파이썬 환경에서 로컬 게임과 백업을 실행한다."""
import argparse
import json
import os
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="신수 로컬 서버와 백업")
    parser.add_argument("command", choices=["run","backup"])
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
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
