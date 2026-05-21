#ifndef RESULT_WRITER_H
#define RESULT_WRITER_H

typedef struct {
    int executed;           // 標記此階段是否有執行 (1: 有, 0: 無)
    int exit_code;          // 程式的回傳碼或 Signal 碼
    char stdout_buf[4096];  // 標準輸出緩衝區
    char stderr_buf[4096];  // 標準錯誤緩衝區
} StageResult;

void write_combined_json(const char *job_id, StageResult *comp, StageResult *exec);

#endif 