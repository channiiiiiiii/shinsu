"""실제 브라우저에서 두 계정의 모바일 플레이 흐름을 검사한다."""
import socket
import tempfile
import threading
import time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright, expect
from shisu.api.main import create_app


def main():
    root = Path(__file__).resolve().parents[1]
    local = root / '.local'
    local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=local) as temporary:
        accounts = {f'player{i}':{'name':f'검증 테이머{i}','code':str(i)*32} for i in (1,2)}
        app = create_app(Path(temporary)/'test.sqlite3',accounts,False)
        sock = socket.socket()
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app,log_level='error'))
        thread = threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(.05)
            assert server.started
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge',headless=True)
                context = browser.new_context(viewport={'width':390,'height':844})
                page = context.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{port}')
                page.locator('#login-form input').fill('1'*32)
                page.get_by_role('button',name='우리 신수 만나러 가기 →').click()
                page.locator('#game').wait_for(state='visible')
                expect(page.locator('#pet-art')).to_be_visible()
                assert page.locator('#pet-art').evaluate('image => image.complete && image.naturalWidth > 0')
                page.locator('[data-tab="adventure"]').click()
                page.locator('[data-action="dungeon"]').first.click()
                expect(page.locator('#message')).to_contain_text('탐험 완료')
                page.locator('[data-tab="bag"]').click()
                assert page.locator('#gems [data-action="equip_gem"]').count()>=1
                page.locator('#gems [data-action="equip_gem"]').first.click()
                expect(page.locator('#message')).to_contain_text('장착했습니다')
                page.locator('[data-tab="pet"]').click()
                page.screenshot(path=str(local/'mobile-preview.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                page.locator('#logout').click()
                page.locator('#login').wait_for(state='visible')
                page.locator('select[name="account"]').select_option('player2')
                page.locator('#login-form input').fill('2'*32)
                page.get_by_role('button',name='우리 신수 만나러 가기 →').click()
                page.locator('#game').wait_for(state='visible')
                page.locator('[data-tab="bag"]').click()
                assert '1,000G' in page.locator('#coins').inner_text()
                assert page.locator('#gems [data-action="equip_gem"]').count()==0
                assert not errors, errors
                browser.close()
                print('모바일 로그인·던전·보석 장착·로그아웃·두 계정 격리 검증 통과')
        finally:
            server.should_exit=True
            thread.join(timeout=10)
            sock.close()


if __name__=='__main__':
    main()
