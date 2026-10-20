# 部署與管理入口

本專案已部署於實驗室 Ubuntu／RTX 4070 Ti，公開網址為 [https://140.113.135.113](https://140.113.135.113)。校外行動網路的登入、偵測與 AI 助理已由使用者確認正常；不需要另將整套系統部署到 Vercel。平台選擇已完成。

一般使用者直接依 [使用手冊](README.md) 操作。以下提供伺服器管理員與後續維護者入口。

## 現行架構

```text
校內外瀏覽器 → HTTPS / Caddy → React build
                           └→ FastAPI（127.0.0.1:8000）
                              ├→ MySQL（127.0.0.1:13306）
                              ├→ YOLO / GPU / 核准模型
                              └→ Ollama（127.0.0.1:11434）
維護診斷 → nginx（127.0.0.1:8080）→ 同一 FastAPI
```

Caddy／backend／nginx 由本專案 Compose 管理；MySQL 使用既有獨立容器，Ollama 使用原生 systemd。`/static` 由後端驗證權限，不能直接公開媒體目錄。Web 不執行 Vite 開發伺服器。

採既有主機與 Ollama，未啟用付費模型或另租雲端運算。電力、磁碟、GPU 與管理仍是共享資源；10–50 位使用者不代表已驗證同時推論量。

## 依情境操作

| 要做的事 | 文件 |
|---|---|
| 查服務、正常啟停、更新與回復 | [目前維運操作](docs/lab-operations.md) |
| 完成尚未執行的每日備份／正式回歸 | [Phase 6 收尾批次](docs/lab-phase6-finalization.md) |
| 查已完成／待驗證的邊界 | [開發與部署狀態](docs/roadmap.md) |
| 查初次 GPU 容器建置問題 | [後端容器專題](docs/lab-backend-container.md) |
| 查 Compose 納管與設定由來 | [Compose 專題](docs/lab-compose.md) |
| 查原始備份／MySQL dump 等價差異 | [備份還原專題](docs/lab-backup.md) |
| 查公開 IP 憑證與 Snap NNP 相容性 | [HTTPS 專題](docs/lab-public-https.md) |
| 查最初的平台評估與診斷 | [歷史部署診斷](docs/archive/reports/deployment-diagnosis-20261020.md) |

**目前尚待 Ubuntu 收尾報告；每日 23:30 排程不能先視為已啟用。** 最初成功還原基準與 Mac 副本已完成，新版完整備份的驗證與下載仍須依收尾文件完成。

## 操作邊界

- 專案帳號、Ubuntu 帳號與 MySQL 帳號不同，請勿混用。
- 正式帳密／模型／媒體／私人報告不放 Git；`.pt` 與 Ollama 模型需要另行交付。
- 專題內的初次建置／納管指令只供追溯，不是日常更新方式；不要重跑已完成的舊更新包。
- 共享主機不重啟 Docker daemon／驅動／整機，不停止其他人的服務，不使用 `down -v` 或全域清理。
- 遇到問題先讀目前維運流程與本輪報告，不覆蓋正式 DB、不略過 HTTPS 驗證。

全部文件的用途與歷史區域見 [文件索引](docs/README.md)。
