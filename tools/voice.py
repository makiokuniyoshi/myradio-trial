#!/usr/bin/env python3
"""原稿(drafts/*.draft.json)を 1 文ずつ音声合成し、1 本の mp3 とタイミング入りの台本を作る。

字幕の時刻は、文ごとの音声の長さを積み上げて決める(音声認識は使わない)。
usage: tools/voice.py drafts/2026-11-06-ja.draft.json [--root DIR] [--backend voicevox|say] [--speaker 2] [--speed 1.1]
--backend say は macOS 標準の声でのローカル確認専用。公開用の局に書かないよう --root の指定を必須にしている。
"""
import argparse, datetime, json, subprocess, sys, tempfile, urllib.parse, urllib.request, wave
from pathlib import Path

ENGINE = "http://127.0.0.1:50021"
RATE = 24000
LEAD, GAP, PART_GAP, TAIL = 0.6, 0.25, 1.05, 2.05


def post(path, params, body=None):
    url = f"{ENGINE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=body or b"", method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def voicevox(text, out, a):
    query = json.loads(post("/audio_query", {"text": text, "speaker": a.speaker}))
    query.update(speedScale=a.speed, outputSamplingRate=RATE, prePhonemeLength=0.05, postPhonemeLength=0.05)
    out.write_bytes(post("/synthesis", {"speaker": a.speaker}, json.dumps(query).encode()))


def say(text, out, a):
    subprocess.run(["say", "-v", "Kyoko", "-r", "210", "-o", str(out), "--file-format=WAVE", f"--data-format=LEI16@{RATE}", text], check=True)


def lines_of(ep):
    """(part 番号, kind, news の index, 文) を放送順に返す。"""
    yield from ((0, "opening", None, l) for l in ep["opening"])
    for i, n in enumerate(ep["news"]):
        yield from ((i + 1, "news", i, l) for l in n["lines"])
    yield from ((len(ep["news"]) + 1, "closing", None, l) for l in ep["closing"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("--root", type=Path)
    ap.add_argument("--backend", choices=["voicevox", "say"], default="voicevox")
    ap.add_argument("--speaker", type=int, default=2)
    ap.add_argument("--speed", type=float, default=1.1)
    a = ap.parse_args()
    if a.backend == "say" and not a.root:
        sys.exit("--backend say はローカル確認専用です。--root に公開用でない場所を指定してください")
    root = (a.root or Path(__file__).resolve().parent.parent).resolve()
    ep = json.loads(a.draft.read_text(encoding="utf-8"))
    name = f"{ep['date']}-{ep['lang']}"
    make = voicevox if a.backend == "voicevox" else say

    pcm, timed, segs, t, prev = bytearray(), [], [], 0.0, None
    silence = lambda s: b"\0\0" * round(s * RATE)
    pcm += silence(LEAD); t = LEAD
    with tempfile.TemporaryDirectory() as tmp:
        for n, (part, kind, idx, line) in enumerate(lines_of(ep)):
            if prev is not None:
                gap = GAP if part == prev else PART_GAP
                pcm += silence(gap); t += gap
            if part != prev:
                if segs:
                    segs[-1]["end"] = round(t, 3)
                segs.append({"kind": kind, "index": idx, "start": round(t, 3), "end": None})
            f = Path(tmp) / f"{n}.wav"
            make(line["say"], f, a)
            with wave.open(str(f)) as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
                    sys.exit(f"想定外の音声形式: {w.getparams()}")
                frames = w.readframes(w.getnframes())
            pcm += frames
            end = t + len(frames) / 2 / RATE
            timed.append({"start": round(t, 3), "end": round(end, 3), "show": line["show"], "part": part})
            t, prev = end, part
        pcm += silence(TAIL)

        raw = Path(tmp) / "all.wav"
        with wave.open(str(raw), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(bytes(pcm))
        mp3 = root / "audio" / f"{name}.mp3"
        mp3.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ar", str(RATE), "-ac", "1", "-b:a", "64k", str(mp3)], check=True)

    seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)]))
    segs[-1]["end"] = round(seconds, 3)
    ep.update(seconds=round(seconds, 2), lines_timed=timed, segments=segs,
              made_at=datetime.datetime.now().isoformat(timespec="seconds"))
    (root / "episodes").mkdir(exist_ok=True)
    (root / "episodes" / f"{name}.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    listing = root / "episodes.json"
    eps = json.loads(listing.read_text(encoding="utf-8")) if listing.exists() else []
    row = next((e for e in eps if e["date"] == ep["date"]), None)
    if row is None:
        row = {"date": ep["date"]}; eps.append(row)
    row[ep["lang"]] = {"title": ep["title"], "seconds": ep["seconds"]}
    eps.sort(key=lambda e: e["date"], reverse=True)
    listing.write_text(json.dumps(eps, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name}: {seconds:.2f}s, {len(timed)} lines, {mp3.stat().st_size} bytes -> {mp3}")


if __name__ == "__main__":
    main()
