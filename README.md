# あさラジ試験放送

[myradio](https://github.com/monoradio102/myradio) テンプレートから作った試験局です。原稿は AI が作成し、合成音声で読み上げます。

- 放送：https://makiokuniyoshi.github.io/myradio-trial/
- 声：VOICEVOX:四国めたん
- キャラ：テンプレート同梱のキャラをそのまま使用（AI 生成）
- ニュースの画像：各サイトの OGP を直接表示し、記事へのリンクを添えています。

## 回の作り方

1. `drafts/<日付>-ja.draft.json` に原稿を書く（`say` は読み上げ用、`show` は字幕用）
2. VOICEVOX Engine を `127.0.0.1:50021` で起動する
3. `python3 tools/voice.py drafts/<日付>-ja.draft.json` で音声とタイミングを作る
4. `tools/publish.sh` で公開する（2 回目以降は force push になるので `PUBLISH_FORCE=1` が要る）

## ライセンス

プログラムは MIT License、詳細は `LICENSE` を参照してください。テンプレートの作者は monoradio102 です。
