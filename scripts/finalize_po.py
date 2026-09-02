#!/usr/bin/env python3
"""翻訳後の仕上げ: 当方が訳を入れたエントリのfuzzy解除+最終検証レポート。

fuzzyフラグが残っているとgettext実行時に訳が使われない。ただし
無差別に外すと「翻訳に失敗して旧fuzzy訳が残った」エントリの古い訳が
生きてしまうため、原本poと比較して msgstr を当方が変更したものだけ外す。
使い方: finalize_po.py <po> <original_po>
"""
import re, sys
import polib

PH = re.compile(r"%\{[^}]+\}|#\{[^}]+\}|%[sd]|</?[a-zA-Z][^>]*>|https?://\S+|\n")

po = polib.pofile(sys.argv[1])
orig = polib.pofile(sys.argv[2])
om = {(e.msgid, e.msgctxt): e for e in orig}
defuzz = ph_ng = 0
for e in po:
    o = om.get((e.msgid, e.msgctxt))
    changed = o is not None and e.msgstr != o.msgstr
    if changed and "fuzzy" in e.flags:
        e.flags.remove("fuzzy"); defuzz += 1
    if e.msgstr and sorted(PH.findall(e.msgid)) != sorted(PH.findall(e.msgstr)):
        ph_ng += 1
        print("PH不一致:", e.msgid[:70].replace("\n", "\\n"))
po.save(sys.argv[1])
t = sum(1 for e in po if e.translated())
print(f"fuzzy解除 {defuzz} 件 / プレースホルダ不一致 {ph_ng} 件")
print(f"最終カバレッジ: {t}/{len(po)} = {t/len(po)*100:.1f}%")
