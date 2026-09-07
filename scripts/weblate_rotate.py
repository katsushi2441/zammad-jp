#!/usr/bin/env python3
"""translations.zammad.org (Weblate) の資格情報を点検・ローテーションする。

  check   : .env の各候補パスワードでログイン可否、API トークンの有効性を表示（値は出さない）
  rotate  : ログインできたセッションで API トークンを再生成し、パスワードも変更して .env を更新

秘密は標準出力に出さない。.env はリポジトリ管理外（.gitignore）。
実行: /home/kojima/work/kgeo/.venv/bin/python scripts/weblate_rotate.py check|rotate
"""
import asyncio, os, re, secrets, sys, urllib.request, urllib.error
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "https://translations.zammad.org"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ENV_FILES = [".env", ".env.prev", ".env.local.bak"]


def load(path):
    d = {}
    if not os.path.exists(path):
        return d
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"')
    return d


def api_status(token):
    req = urllib.request.Request(f"{HOST}/api/users/{USER}/", headers={"Authorization": "Token " + token, "User-Agent": UA})
    try:
        return urllib.request.urlopen(req, timeout=30).status
    except urllib.error.HTTPError as e:
        return e.code


envs = {f: load(os.path.join(ROOT, f)) for f in ENV_FILES}
USER = next((e["WEBLATE_USER"] for e in envs.values() if e.get("WEBLATE_USER")), "katsushi2441")


async def login(pg, ctx, pw):
    await ctx.clear_cookies()
    await pg.goto(HOST + "/accounts/login/", wait_until="networkidle", timeout=60000)
    await pg.fill('input[name="username"]', USER)
    await pg.fill('input[name="password"]', pw)
    await pg.click('form[action="/accounts/login/"] [type=submit]')
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    return "/accounts/login" not in pg.url


async def main(cmd):
    cands = []
    for f, e in envs.items():
        if e.get("WEBLATE_PASSWORD") and e["WEBLATE_PASSWORD"] not in [c[1] for c in cands]:
            cands.append((f, e["WEBLATE_PASSWORD"]))
    toks = []
    for f, e in envs.items():
        if e.get("WEBLATE_API_KEY") and e["WEBLATE_API_KEY"] not in [t[1] for t in toks]:
            toks.append((f, e["WEBLATE_API_KEY"]))
    for f, t in toks:
        print(f"APIトークン({f}, {len(t)}文字) → HTTP {api_status(t)}")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(locale="ja-JP", user_agent=UA)
        pg = await ctx.new_page()
        active = None
        for f, pw in cands:
            ok = await login(pg, ctx, pw)
            print(f"ログイン({f} のパスワード, {len(pw)}文字) → {'OK' if ok else 'NG'}")
            if ok and not active:
                active = pw
        if cmd == "check" or not active:
            if not active:
                print("ログインできる候補なし")
            await b.close()
            return
        await login(pg, ctx, active)
        # --- API トークン再生成 ---
        await pg.goto(HOST + "/accounts/profile/#api", wait_until="networkidle", timeout=60000)
        before = set(re.findall(r"wlu_[A-Za-z0-9]{20,}", await pg.content()))
        csrf = await pg.evaluate("(document.querySelector('input[name=csrfmiddlewaretoken]')||{}).value||''")
        st = await pg.evaluate(
            "(async(c)=>{const r=await fetch('/accounts/reset-api-key/',{method:'POST',headers:{'X-CSRFToken':c,'Content-Type':'application/x-www-form-urlencoded'},body:'csrfmiddlewaretoken='+encodeURIComponent(c),credentials:'include'});return r.status;})",
            csrf,
        )
        await pg.goto(HOST + "/accounts/profile/#api", wait_until="networkidle", timeout=60000)
        after = set(re.findall(r"wlu_[A-Za-z0-9]{20,}", await pg.content()))
        new_tok = sorted(after - before)
        print(f"reset-api-key POST → HTTP {st} / 新トークン取得: {bool(new_tok)} / 旧トークン残存: {bool(before & after)}")
        # --- パスワード変更 ---
        new_pw = secrets.token_urlsafe(18)
        await pg.goto(HOST + "/accounts/password/", wait_until="networkidle", timeout=60000)
        names = await pg.evaluate("Array.from(document.querySelectorAll('form input')).map(e=>e.name).filter(Boolean)")
        for n, v in (("old_password", active), ("new_password1", new_pw), ("new_password2", new_pw)):
            if n in names:
                await pg.fill(f'input[name="{n}"]', v)
        await pg.click('input[name="new_password1"] >> xpath=ancestor::form//*[@type="submit"]')
        await pg.wait_for_load_state("networkidle")
        await pg.wait_for_timeout(1500)
        errs = await pg.evaluate("Array.from(document.querySelectorAll('.errorlist li,.alert-danger,.has-error .help-block,.invalid-feedback,.text-danger')).map(e=>e.textContent.trim()).filter(Boolean)")
        pw_ok = await login(pg, ctx, new_pw)
        print(f"パスワード変更: {'OK' if pw_ok else 'NG'} errors={errs[:3]}")
        final_pw = new_pw if pw_ok else active
        base = envs[".env"] or next(iter(envs.values()))
        base = dict(base, WEBLATE_USER=USER, WEBLATE_PASSWORD=final_pw)
        if new_tok:
            base["WEBLATE_API_KEY"] = new_tok[0]
        for f in ENV_FILES:
            with open(os.path.join(ROOT, f), "w", encoding="utf-8") as fh:
                for k in ("WEBLATE_USER", "WEBLATE_EMAIL", "WEBLATE_PASSWORD", "WEBLATE_API_KEY"):
                    if k in base:
                        fh.write(f"{k}={base[k]}\n")
        print(".env 更新: パスワード=" + ("新" if pw_ok else "従来") + " / トークン=" + ("新" if new_tok else "従来"))
        for f, t in toks:
            print(f"旧トークン({f}) → HTTP {api_status(t)}")
        if new_tok:
            print(f"新トークン → HTTP {api_status(new_tok[0])}")
        await b.close()


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "check"))
