#!/bin/bash
# 日本語翻訳

[[ -n "${_I18N_JA_LOADED:-}" ]] && return 0
declare -r _I18N_JA_LOADED=1

declare -gA _I18N_JA=(
    # ── 共通ステータス ──
    [status.set]="設定済み"
    [status.not_set]="未設定"
    [status.enabled]="有効"
    [status.not_enabled]="無効"
    [status.added]="追加済み"
    [status.not_needed]="不要"
    [status.cancelled]="キャンセル済み"

    # ── 入力検証 ──
    [validate.username.empty]="ユーザー名は空にできません"
    [validate.username.format]="小文字英字、数字、アンダースコア、ハイフンのみ使用可能"

    # ── ミラー ──
    [mirror.no_reflector]="reflector 未インストール、内蔵ミラーリストを使用"
    [mirror.fetching]="reflector で中国ミラーを取得中 (速度順)..."
    [mirror.fetch_failed]="reflector 取得失敗、内蔵ミラーリストを使用"
    [mirror.no_results]="reflector がミラーを返さず、内蔵リストを使用"
    [mirror.found]="%s 個のミラーを取得 (速度順)"

    # ── ナビゲーション (ウィザードステップ名 & 進捗ラベル) ──
    [nav.lang]="言語"
    [nav.disk]="ディスク"
    [nav.net]="ネットワーク"
    [nav.repos]="リポジトリ"
    [nav.gpu]="GPU"
    [nav.user]="ユーザー名"
    [nav.passwd]="パスワード"
    [nav.root]="Rootパスワード"
    [nav.confirm]="確認"

    # ── ステップタイトル (fzf / 入力プロンプト) ──
    [step.lang.title]="システム言語"
    [step.disk.title]="インストール先ディスク"
    [step.net.title]="ネットワークバックエンド"
    [step.gpu.title]="GPUドライバー"
    [step.user.title]="ユーザー名"
    [step.passwd.title]="ユーザーパスワード"
    [step.root.title]="Root パスワード (空欄 = 設定なし)"

    # ── ステップメッセージ ──
    [step.lang.success]="言語: %s"
    [step.lang.kmscon]="非英語 TTY 表示のため %s を自動追加"
    [step.disk.success]="インストール先: %s"
    [step.net.success]="ネットワーク: %s"
    [step.repos.confirm]="multilib リポジトリを有効にしますか？ (32ビット互換、Steam等)"
    [step.repos.enabled]="multilib: 有効"
    [step.repos.disabled]="multilib: 無効"
    [step.gpu.success]="GPUドライバー: %s"
    [step.gpu.mesa_only]="GPUドライバー: mesa のみ (汎用)"
    [step.gpu.mesa_generic]="mesa (汎用)"
    [step.user.success]="ユーザー名: %s"
    [step.passwd.empty]="ユーザーパスワードは空にできません"
    [step.root.set]="Root パスワード: 設定済み"
    [step.root.unset]="Root パスワード: 未設定"

    # ── 確認ステップ ──
    [confirm.lang]="システム言語"
    [confirm.disk]="ディスク"
    [confirm.net]="ネットワーク"
    [confirm.gpu]="GPUドライバー"
    [confirm.user]="ユーザー名"
    [confirm.root]="Rootパスワード"
    [confirm.version]="バージョン"
    [confirm.prompt]="この設定で正しいですか？JSONファイルを生成しますか？"
    [confirm.preview_title]="設定概要"

    # ── 固定サマリー項目 ──
    [fixed.boot]="ブート"
    [fixed.fs]="FS"
    [fixed.audio]="オーディオ"
    [fixed.bt]="BT"

    # ── 生成完了 ──
    [post.title]="ファイル生成完了"
    [post.sys_config]="(システム設定)"
    [post.credentials]="(認証情報)"
    [post.kmscon_hint]="ヒント: 初回起動後、デフォルトTTYの代わりにkmsconを有効にしてください:"

    # ── ISOインストール ──
    [iso.title]="インストール"
    [iso.detected]="Arch Linux ISO インストール環境を検出"
    [iso.run_now]="今すぐ archinstall を実行しますか？"
    [iso.mount_not_found]="マウントポイントが見つかりません、手動でkmsconを有効にしてください:"
    [iso.complete_title]="インストール完了"
    [iso.success]="システムのインストールが成功しました"
    [iso.reboot]="新しいシステムで再起動:"

    # ── ウィザードエンジン ──
    [wizard.first_step]="最初のステップです"
    [wizard.aborted]="中止しました"
    [wizard.step_failed]="ステップ '%s' が失敗しました (exit %s)"

    # ── オプションラベル (動的配列構築) ──
    [opt.lang.zh_CN]="簡体中文  zh_CN.UTF-8"
    [opt.lang.en_US]="English   en_US.UTF-8"
    [opt.lang.ja_JP]="日本語    ja_JP.UTF-8"
    [opt.net.nm_iwd]="NetworkManager + iwd  (推奨、省電力)"
    [opt.net.nm]="NetworkManager + wpa_supplicant  (レガシー)"
)
