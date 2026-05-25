# AI Sandbox 安全程式碼執行平台

本專案實作一套用於執行不可信程式碼的 sandbox 系統。使用者提交 C 或 Python 程式後，系統會為每個 Job 建立獨立的 runtime 目錄，透過 OverlayFS 組合 rootfs 與語言環境，並在隔離後的 namespace 中執行程式。執行期間會套用 CPU、記憶體、Process、檔案大小、系統呼叫等限制，最後將編譯與執行結果輸出成 JSON，供後端或前端讀取。

---

## 1. Rootfs / Image 建構腳本使用說明

本系統的 sandbox rootfs 放在：

```bash
./sandbox/image/
```

主要包含三種目錄：

```bash
./sandbox/image/base_rootfs   # Alpine minimal rootfs
./sandbox/image/gcc           # GCC environment layer
./sandbox/image/python        # Python runtime environment layer
```

### 1.1 一次建立所有 rootfs / image

建議第一次設定環境時直接執行：

```bash
chmod +x scripts/*.sh
sudo bash scripts/build_all.sh
```

`build_all.sh` 會依序完成：

1. 建立 Alpine `base_rootfs`
2. 建立 GCC 語言層
3. 建立 Python 語言層
4. 清理 base rootfs 中不必要的執行檔目錄 (確保 rootfs 最小化)
5. 重新建立 sandbox 執行時需要的基本目錄，例如 `bin`、`lib`、`tmp`、`dev`
6. 設定 `/tmp` 權限為 `1777`

---

### 1.2 單獨建立 Alpine base_rootfs

如果只想重新建立最基礎的 rootfs，可以執行：

```bash
sudo bash scripts/build_rootfs.sh
```

此腳本會下載 Alpine Minirootfs，解壓縮到：

```bash
./sandbox/image/base_rootfs
```

並建立 `/tmp` 目錄，設定標準暫存目錄權限：

```bash
chmod 1777 ./sandbox/image/base_rootfs/tmp
```

---

### 1.3 建立指定語言環境

如果只想重建某個語言層，可以使用：

```bash
sudo bash scripts/build_image.sh gcc
```

或：

```bash
sudo bash scripts/build_image.sh python
```

`build_image.sh` 的流程如下：

1. 複製 `base_rootfs` 到暫存 rootfs
2. bind mount `/dev`、`/proc`、`/sys` 進暫存 rootfs
3. 使用 `chroot` 進入暫存 rootfs
4. 依照參數安裝需要的套件：
   - `gcc`：安裝 `gcc`、`musl-dev`
   - `python`：安裝 `python3`
5. 使用 `rsync --compare-dest` 產生與 `base_rootfs` 不同的差異層
6. 將結果輸出到：
   - `./sandbox/image/gcc`
   - `./sandbox/image/python`

---

## 2. Sandbox 防禦機制說明

本系統的防禦設計不是只依賴單一機制，而是結合 namespace、OverlayFS、pivot_root、cgroup、rlimit、seccomp、權限下降與輸出控管，形成多層防護。

---

### 2.1 Namespace 隔離

sandbox 會使用 `clone()` 建立新的隔離環境，包含：

```c
CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER
```

各 namespace 的用途如下：

| Namespace | 功能 |
|---|---|
| PID Namespace | 讓 sandbox 內的程式看不到主機上的其他 process |
| Mount Namespace | 讓 sandbox 擁有獨立的檔案系統掛載視角 |
| Network Namespace | 預設隔離網路，避免使用者程式直接存取外部網路 |
| User Namespace | 將 sandbox 內的 root 對應到主機上的一般使用者 UID/GID |

User namespace 會透過 `/proc/<pid>/uid_map` 與 `/proc/<pid>/gid_map` 建立 UID/GID 對應，使 sandbox 內看似 root，但在主機上仍對應到一般使用者，降低權限擴散風險。

---

### 2.2 Mount Namespace 與 rootfs 隔離

系統會先呼叫：

```c
mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)
```

將 mount propagation 設為 private，避免 sandbox 內部的 mount 操作影響到主機或其他 sandbox。

接著會透過 OverlayFS 建立每個 Job 專屬的 rootfs：

```bash
lowerdir = 語言層 : base_rootfs
upperdir = /tmp/sandbox/job_<job_id>/upper
workdir  = /tmp/sandbox/job_<job_id>/work
merged   = /tmp/sandbox/job_<job_id>/merged
```

C 語言 Job 會使用：

```bash
lowerdir=./sandbox/image/gcc:./sandbox/image/base_rootfs
```

Python Job 會使用：

```bash
lowerdir=./sandbox/image/python:./sandbox/image/base_rootfs
```

這樣做的目的：

1. `base_rootfs` 與語言層可以重複使用
2. 每個 Job 都有自己的 `upperdir`
3. 使用者程式造成的檔案變更只會留在該 Job 的 runtime 目錄
4. Job 結束後可以直接清理 `/tmp/sandbox/job_<job_id>`

---

### 2.3 pivot_root 切換根目錄

OverlayFS 掛載完成後，sandbox 會使用 `pivot_root()` 將程式看到的 `/` 切換到該 Job 的 `merged` rootfs。

流程大致如下：

1. 將 `merged` bind mount 到自己身上，確保它是可作為 root 的 mount point
2. `chdir()` 到 `merged`
3. 建立 `.oldroot`
4. 呼叫 `pivot_root(".", "./.oldroot")`
5. 切換到新的 `/`
6. 將舊根目錄 `/.oldroot` 卸載並移除

這樣使用者程式在 sandbox 內看到的 `/` 就不是主機的根目錄，而是專屬於該 Job 的 rootfs。

---

### 2.4 受控的 bind mount

切換 rootfs 後，系統只把必要目錄掛進 sandbox：

| Sandbox 內路徑 | 用途 |
|---|---|
| `/app` | 放置使用者提交的 `main.c`、`main.py` 與編譯後的 `user_program` |
| `/output` | 儲存程式執行輸出，例如 `output.txt` |
| `/tmp` | 提供編譯器或執行階段需要的暫存空間 |
| `/proc` | 提供必要的 process 資訊，並使用 `MS_NOSUID | MS_NODEV | MS_NOEXEC` 掛載 |

這樣可以避免直接暴露主機上的任意目錄，只開放 sandbox 執行所需的最小範圍。

---

### 2.5 Resource Limit：rlimit

sandbox 會使用 `setrlimit()` 對程式套用基本資源限制：

| 限制項目 | 使用的 rlimit | 目的 |
|---|---|---|
| CPU 時間 | `RLIMIT_CPU` | 避免程式長時間佔用 CPU |
| 記憶體位址空間 | `RLIMIT_AS` | 限制程式可使用的記憶體大小 |
| 檔案描述符數量 | `RLIMIT_NOFILE` | 避免大量開啟 fd |
| Process 數量 | `RLIMIT_NPROC` | 避免 fork bomb |
| 輸出檔案大小 | `RLIMIT_FSIZE` | 避免產生過大的輸出檔 |

目前程式中固定的部分限制包含：

```c
NOFILE_LIMIT   = 32
NPROC_LIMIT    = 16
FILESIZE_LIMIT = 1 MB
```

CPU timeout 與 memory limit 則會由執行 sandbox 時的參數傳入。

---

### 2.6 cgroup 資源控管

除了 `rlimit` 外，系統也會使用 cgroup v2 進一步限制整個 sandbox process group 的資源。

每個 Job 會建立獨立的 cgroup：

```bash
/sys/fs/cgroup/sandbox/<job_id>
```

並寫入：

```bash
cpu.max
memory.max
pids.max
cgroup.procs
```

用途如下：

| cgroup 檔案 | 功能 |
|---|---|
| `cpu.max` | 限制 CPU quota，例如 0.5 core、1 core |
| `memory.max` | 限制整個 Job 可用的記憶體 |
| `pids.max` | 限制 process/thread 數量 |
| `cgroup.procs` | 將 sandbox process 加入該 cgroup |

`rlimit` 偏向限制單一 process；cgroup 則能限制整個 Job，對 fork 出來的子行程也會有更完整的資源控制效果。

---

### 2.7 Wall-clock Timeout

除了 `RLIMIT_CPU` 以外，parent process 也會用 `clock_gettime(CLOCK_MONOTONIC)` 計算實際經過時間。

如果執行時間超過使用者設定的 timeout：

```c
kill(pid, SIGKILL);
```

系統會將結果標示為：

```text
Time Limit Exceeded (TLE)
```

這可以處理 sleep、I/O blocking 等不一定消耗大量 CPU，但實際執行時間過久的情況。

---

### 2.8 Seccomp 系統呼叫限制

Sandbox 的 seccomp 規則設計參考 Docker 預設 seccomp profile，採用 blacklist 方式進行 syscall 過濾。也就是預設允許一般程式執行所需的 syscall，但針對可能造成沙盒逃逸、系統狀態修改或核心層級操作的高風險 syscall 進行封鎖。

| 類型 |  syscall | 防禦目的 |
|---|---|---|
| namespace / mount escape | `mount`, `umount2`, `pivot_root`, `setns`, `unshare` | 避免使用者程式重新掛載檔案系統、切換 namespace 或嘗試逃逸 sandbox |
| kernel module | `init_module`, `finit_module`, `delete_module` | 避免載入或移除核心模組 |
| process inspection | `ptrace`, `process_vm_readv`, `process_vm_writev`, `kcmp` | 避免偵測、追蹤或讀寫其他 process |
| file handle | `open_by_handle_at`, `name_to_handle_at` | 避免透過特殊 file handle 繞過一般路徑權限檢查 |
| io_uring | `io_uring_setup`, `io_uring_enter`, `io_uring_register` | 降低新型非同步 I/O 介面造成的攻擊面 |
| BPF / perf | `bpf`, `perf_event_open` | 避免觀察 kernel 層資訊或建立高風險 tracing 能力 |
| keyring | `add_key`, `keyctl`, `request_key` | 避免操作 kernel keyring |
| reboot / swap | `reboot`, `swapon`, `swapoff` | 避免影響主機開關機或 swap 狀態 |
| time modification | `clock_settime`, `settimeofday`, `stime` | 避免修改系統時間 |
| kernel loading | `kexec_load` | 避免載入新的 kernel 映像 |
| memory policy | `set_mempolicy`, `mbind`, `move_pages` | 避免調整底層記憶體配置策略 |
| legacy syscall | `_sysctl`, `sysfs`, `uselib`, `ustat`, `vm86`, `vm86old` | 關閉不必要且風險較高的舊介面 |
| userfaultfd | `userfaultfd` | 降低使用者態 page fault 處理機制造成的攻擊面 |
| personality | `personality` | 避免修改 process 執行特性或相容模式 |

如果使用者程式呼叫被封鎖的 syscall，會被 seccomp 終止，結果會被記錄為：

```text
Seccomp Blocked Syscall
```

---

### 2.9 權限下降與環境清理

在**真正執行使用者程式**前，sandbox 會進一步降低權限：

```c
setgid(1000);
setuid(1000);
```

同時清空環境變數：

```c
clearenv();
setenv("PATH", "/bin:/usr/bin", 1);
```

這樣可以避免使用者程式繼承主機或 parent process 中不必要的環境變數，也能減少透過環境變數影響執行流程的可能性。

另外，sandbox 會**關閉多餘的檔案描述**符，減少使用者程式繼承 parent process fd 的風險。

---

### 2.10 結果輸出與 JSON 安全處理

執行結果會輸出到：

```bash
./sandbox/result/job_<job_id>/
```

主要包含：

```bash
result.json   # 編譯與執行結果
output.txt    # 使用者程式 stdout
monitor.log   # 執行期間的資源監控紀錄
```

`result.json` 會包含：

```json
{
  "compile": {
    "exit_code": 0,
    "status_message": "Success",
    "stdout": "",
    "stderr": ""
  },
  "execute": {
    "exit_code": 0,
    "status_message": "Normal Exit",
    "stdout": "",
    "stderr": "",
    "time_ms": 0,
    "memory_kb": 0
  }
}
```


---

## 3. 編譯與啟動 Sandbox

### 3.1 安裝必要套件

在 Ubuntu / WSL 環境下，可以先安裝：

```bash
sudo apt update
sudo apt install -y build-essential make libseccomp-dev wget rsync
```

如果系統缺少其他開發套件，再依編譯錯誤補上。

---

### 3.2 建立 rootfs / image

第一次執行前，請先建立 sandbox image：

```bash
sudo bash scripts/build_all.sh
```

確認以下目錄存在：

```bash
ls sandbox/image
```

應可看到：

```bash
base_rootfs  gcc  python
```

---

### 3.3 編譯 sandbox

若 Makefile 位在專案根目錄：

```bash
make
```
編譯完成後，sandbox binary 預期位於類似位置：

```bash
./sandbox/build/sandbox
```
## 4. 執行流程摘要

整體 Sandbox 流程會從執行以下指令開始：

```bash
sudo sandbox/build/sandbox <job_id> <language> <cpu_core> <memory_mb> <timeout_sec>
```

各參數用途如下：

| 參數 | 說明 |
|---|---|
| `job_id` | Job 編號，只允許英數字、底線 `_`、減號 `-` |
| `language` | 程式語言，目前支援 `c`、`python` |
| `cpu_core` | CPU core 限制，例如 `1.0`、`0.5` |
| `memory_mb` | 記憶體限制，單位 MB |
| `timeout_sec` | wall-clock timeout，單位秒 |

例如：

```bash
sudo sandbox/build/sandbox 154 c 1.0 256 10
```

執行後，系統會依照指定的 `job_id` 建立該次任務的獨立 Sandbox 環境，並根據傳入的語言與資源限制套用對應設定，流程如下：

```text
Parent Process                                      Child Process
────────────────────────────────────────────────    ────────────────────────────────────────────────
解析參數、建立 runtime 目錄
        ↓
選擇 rootfs layer 並掛載 OverlayFS
        ↓
建立 pipe 並呼叫 clone()          ───────────────▶    進入 namespace
        ↓                                                  ↓
設定 UID/GID map、加入 cgroup                          等待 parent 同步
        ↓                                                  ↓
送出同步訊號                  ───────────────────▶   pivot_root 切換 rootfs
        ↓                                                  ↓
監控執行狀態與資源使用量                                套用 rlimit 與 seccomp
        ↓                                                  ↓
收集 stdout / stderr                                 執行 compile stage
        ↓                                                  ↓
等待 child 結束                  ◀────────────────── 執行 execute stage
        ↓                                                  ↓
寫入 result.json / output.txt / monitor.log            回傳 exit code
        ↓
清理 /tmp/sandbox/job_<job_id>
```

---

## 5. 注意事項

- rootfs 建構過程會使用 `chroot` 與 bind mount，若腳本中斷，可以手動檢查是否有殘留掛載點。
- 每個 Job 的 runtime 目錄會建立在 `/tmp/sandbox/job_<job_id>`，正常結束後會自動清理。
- 執行結果會保存在 `./sandbox/result/job_<job_id>`。

