#!/usr/bin/env python3
"""Zammadのja.po未訳エントリをDeepSeek v4-flashで翻訳する。

- プレースホルダ(%s, %{x}, #{x}, HTMLタグ, URL, 改行)は逐語保持し、検証NGは採用しない
- 進捗はincrementalに保存(再実行で続きから)
使い方: translate_po.py <po> [--limit N] [--dry]
"""
import json, re, sys, time
import polib, requests

KCBRAIN_ENV = "/home/kojima/work/kcbrain/.env"
def _env(k, d=""):
    for line in open(KCBRAIN_ENV, encoding="utf-8"):
        if line.startswith(k + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return d
KEY = _env("KCBRAIN_DEEPSEEK_API_KEY")
BASE = _env("KCBRAIN_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = _env("KCBRAIN_DEEPSEEK_MODEL", "deepseek-v4-flash")

PH = re.compile(r"%\{[^}]+\}|#\{[^}]+\}|%[sd]|</?[a-zA-Z][^>]*>|https?://\S+|\n")
def tokens(s):
    return sorted(PH.findall(s))

SYS = """あなたはヘルプデスクSaaS「Zammad」のUI文言の日英翻訳者です。英語の原文を自然な日本語UIの文言に翻訳してください。

厳守事項:
- プレースホルダ・マークアップは一字も変えずそのまま残す: %s, %{name}, #{ticket.title} などの変数、HTMLタグ、URL、改行(\\n)、Markdown記号
- 固有名詞・製品名・プロトコル名は英語のまま: Zammad, Slack, S/MIME, LDAP, OTRS, Sipgate, i-doit など
- 用語統一: Ticket=チケット / Agent=担当者 / Customer=顧客 / Organization=組織 / Group=グループ / Overview=一覧 / Trigger=トリガー / Macro=マクロ / Owner=所有者 / State=状態 / Priority=優先度 / Article=記事 / Escalation=エスカレーション
- 短いラベルは名詞形、文はですます調
- 出力はJSONのみ: {"items":[{"i":番号,"ja":"訳文"}]}"""

# 内部作業はローカルgemma4を使う(DeepSeekは有料レール専用・2026-09-02指示)。
OLLAMA = "http://192.168.0.3:11434"
GEMMA = "gemma4:12b-it-qat"

def translate_batch(items):
    src = json.dumps({"items": [{"i": i, "en": s} for i, s in items]}, ensure_ascii=False)
    r = requests.post(OLLAMA + "/api/chat", timeout=600, json={
        "model": GEMMA, "stream": False, "think": False, "format": "json",
        "options": {"temperature": 0.2, "num_predict": 4000, "num_ctx": 8192},
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": src}]})
    r.raise_for_status()
    txt = r.json()["message"]["content"]
    out = json.loads(txt)
    return {int(x["i"]): x["ja"] for x in out.get("items", []) if "i" in x and "ja" in x}

def main():
    path = sys.argv[1]
    limit = 0
    if "--limit" in sys.argv: limit = int(sys.argv[sys.argv.index("--limit") + 1])
    po = polib.pofile(path)
    unt = [e for e in po if not e.translated() and not e.obsolete and e.msgid.strip()]
    if limit: unt = unt[:limit]
    print(f"未訳 {len(unt)} 件を翻訳開始 model=gemma4:12b-it-qat(local)", flush=True)
    ok = ng = 0
    B = 8
    for bi in range(0, len(unt), B):
        batch = unt[bi:bi + B]
        items = [(i, e.msgid) for i, e in enumerate(batch)]
        try:
            got = translate_batch(items)
        except Exception as ex:
            print(f"  batch{bi//B}: API失敗 {str(ex)[:80]} → スキップ", flush=True)
            time.sleep(5); continue
        for i, e in enumerate(batch):
            ja = got.get(i)
            if not ja: ng += 1; continue
            if tokens(e.msgid) != tokens(ja):
                ng += 1; continue  # プレースホルダ不一致は不採用
            if e.msgid_plural:
                e.msgstr_plural = {0: ja}
            else:
                e.msgstr = ja
            if "fuzzy" in e.flags:
                e.flags.remove("fuzzy")
            ok += 1
        if (bi // B) % 10 == 0:
            po.save(path)
            print(f"  進捗 {bi+len(batch)}/{len(unt)} 採用{ok} 不採用{ng}", flush=True)
    po.save(path)
    print(f"完了: 採用{ok} 不採用{ng} → {path}", flush=True)

if __name__ == "__main__":
    main()
