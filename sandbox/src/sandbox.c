#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mount.h>
#include <errno.h>
#include <fcntl.h>

#include "limit.h"
#include "namespace.h"
#include "filesystem.h"
#include "sandbox_seccomp.h"
#include "payload.h"
#include "result_writer.h"

#define STACK_SIZE (1024 * 1024)

typedef struct {
    int stdout_pipe[2];
    int stderr_pipe[2];
} ChildPipeArgs;

static char child_stack[STACK_SIZE];
static int sync_pipe[2];
static char *current_job_id = NULL;

void prepare_test_source(const char *job_id){
    char app_dir[512];
    char source_path[512];

    snprintf(app_dir, sizeof(app_dir), "/tmp/sandbox/job_%s/app", job_id);
    snprintf(source_path, sizeof(source_path), "%s/main.c", app_dir);

    if(mkdir(app_dir, 0755) == -1 && errno != EEXIST){
        perror("mkdir app_dir");
        exit(1);
    }

   
    if (chown(app_dir, get_real_uid(), get_real_gid()) == -1) {
        perror("chown app_dir");
    }
    // 檢查檔案是否已經存在，如果 Python Worker 已經寫好檔案，就不要覆寫
    if(access(source_path, F_OK) == 0){
        fprintf(stderr, "[Parent] Test source already exists (Provided by Worker): %s\n", source_path);
        return;
    }

    FILE *fp = fopen(source_path, "w");
    if(fp == NULL){
        perror("fopen source");
        exit(1);
    }

    fprintf(fp,
        "#include <stdio.h>\n"
        "#include <unistd.h>\n"
        "#include <string.h>\n\n"
        "int main() {\n"
        "    printf(\"Hello, sandbox!\\n\");\n"
        "    return 0;\n"
        "}\n"
    );
    fclose(fp);

    // ▼ ▼ ▼ 2. 將預設生成的 main.c 權限交給真實使用者 ▼ ▼ ▼
    if (chown(source_path, get_real_uid(), get_real_gid()) == -1) {
        perror("chown source_path");
    }
    // ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲

    fprintf(stderr, "[Parent] Default test source prepared: %s\n", source_path);
}

static void redirect_compile_output(int out_pipe[2], int err_pipe[2]){
    fflush(stdout);
    fflush(stderr);
    close(out_pipe[0]);
    close(err_pipe[0]);
    dup2(out_pipe[1], STDOUT_FILENO);
    dup2(err_pipe[1], STDERR_FILENO);
    close(out_pipe[1]);
    close(err_pipe[1]);
}

static void redirect_execute_output(int err_pipe[2]){
    // 1. 先將 stderr 導向 Pipe，這樣接下來的 open 若失敗，錯誤才能被 Parent 抓到
    dup2(err_pipe[1], STDERR_FILENO);
    close(err_pipe[0]);
    close(err_pipe[1]);

    // 2. 再嘗試打開檔案重定向 stdout
    const char *out_path = "/output/output.txt";
    int out_fd = open(out_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out_fd == -1) {
        perror("Redirect output open failed");
        exit(1);
    }
    fflush(stdout);
    dup2(out_fd, STDOUT_FILENO);
    close(out_fd);
}

int compile_child_func(void *arg){
    ChildPipeArgs *pipes = (ChildPipeArgs *)arg;
    close(sync_pipe[1]);
    char buf;
    if(read(sync_pipe[0], &buf, 1) == -1){ exit(1); }

    if (setgid(0) == -1) { 
        perror("setgid failed"); 
        exit(1); 
    }
    if (setuid(0) == -1) { 
        perror("setuid failed"); 
        exit(1); 
    }

    setup_mount_namespace();
    setup_pivot_root(current_job_id);
    setup_resource_limits();
    setup_seccomp();
    redirect_compile_output(pipes->stdout_pipe, pipes->stderr_pipe);
    if(compile_program() != 0){ exit(1); }
    return 0;
}

int execute_child_func(void *arg){
    ChildPipeArgs *pipes = (ChildPipeArgs *)arg;
    close(sync_pipe[1]);
    char buf;
    if(read(sync_pipe[0], &buf, 1) == -1){ exit(1); }

    if (setgid(0) == -1) { perror("setgid failed"); exit(1); }
    if (setuid(0) == -1) { perror("setuid failed"); exit(1); }

    setup_mount_namespace();
    setup_pivot_root(current_job_id);
    setup_resource_limits();
    
    redirect_execute_output(pipes->stderr_pipe);
    close(pipes->stdout_pipe[0]); 
    close(pipes->stdout_pipe[1]);

    pid_t p = fork();
    if (p < 0) 
    {
        perror("fork inside namespace failed");
        exit(1);
    }
    if (p == 0) {
        execute_program();
        exit(1); 
    }
    
    int status;
    waitpid(p, &status, 0);
    if (WIFEXITED(status)) {
        exit(WEXITSTATUS(status));
    } else if (WIFSIGNALED(status)) {
        // 若 PID 2 被 Signal 25 殺死，這裡會以 128+25 = 153 退出
        exit(128 + WTERMSIG(status));
    }
    
    exit(1);
}

int run_sandboxed_stage(int (*child_func)(void *), const char *stage_name, StageResult *res){
    res->executed = 1;
    
    // 將 Pipe 宣告為區域變數，確保 Compile 和 Execute 階段的生命週期完全獨立
    ChildPipeArgs pipes; 
    
    if (pipe(sync_pipe) == -1 || pipe(pipes.stdout_pipe) == -1 || pipe(pipes.stderr_pipe) == -1) {
        perror("pipe creation failed");
        return -1;
    }

    int clone_flags = CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER | SIGCHLD;
    
    // 關鍵修改：將區域變數 pipes 的指標作為參數傳入 clone，讓子進程抓到正確的 FD
    pid_t pid = clone(child_func, child_stack + STACK_SIZE, clone_flags, &pipes);

    if (pid == -1) {
        fprintf(stderr, "[Parent] clone %s failed\n", stage_name);
        return -1;
    }

    close(sync_pipe[0]);    // 父進程不讀同步訊號
    close(pipes.stdout_pipe[1]);  // 父進程不寫標準輸出
    close(pipes.stderr_pipe[1]);  // 父進程不寫標準錯誤

    setup_uid_gid_map(pid);
    setup_cgroup(pid);

    if (write(sync_pipe[1], "x", 1) == -1) {
        perror("write sync_pipe");
        return -1;
    }
    close(sync_pipe[1]);

    // 設置為非阻塞模式
    fcntl(pipes.stdout_pipe[0], F_SETFL, fcntl(pipes.stdout_pipe[0], F_GETFL) | O_NONBLOCK);
    fcntl(pipes.stderr_pipe[0], F_SETFL, fcntl(pipes.stderr_pipe[0], F_GETFL) | O_NONBLOCK);

    int status;
    size_t out_total = 0;
    size_t err_total = 0;
    ssize_t n;

    while (1) {
        // 嘗試讀取 stdout (在 execute 階段一讀就會是 0 或者是 EAGAIN，因為已經導向檔案了)
        while (out_total < sizeof(res->stdout_buf) - 1) {
            n = read(pipes.stdout_pipe[0], res->stdout_buf + out_total, sizeof(res->stdout_buf) - out_total - 1);
            if (n > 0) out_total += n;
            else break; 
        }

        // 嘗試讀取 stderr (用來抓 Runtime 崩潰訊息)
        while (err_total < sizeof(res->stderr_buf) - 1) {
            n = read(pipes.stderr_pipe[0], res->stderr_buf + err_total, sizeof(res->stderr_buf) - err_total - 1);
            if (n > 0) err_total += n;
            else break; 
        }

        // 檢查子進程狀態
        pid_t ret = waitpid(pid, &status, WNOHANG);
        if (ret == pid) {
            break; // 子進程乾脆地結束了，跳出大迴圈！
        }
        if (ret == -1) {
            if (errno == EINTR) continue; 
            perror("waitpid");
            return -1;
        }

        // 保持 0.01 秒的睡眠，防止極速空轉，同時給核心足夠的反應時間
        usleep(10000); 
    }

    // 子進程結束後，做最後一輪殘留資料排空 (將 Pipe 內剩餘的資料抽乾)
    while (out_total < sizeof(res->stdout_buf) - 1) {
        n = read(pipes.stdout_pipe[0], res->stdout_buf + out_total, sizeof(res->stdout_buf) - out_total - 1);
        if (n > 0) out_total += n;
        else break;
    }
    while (err_total < sizeof(res->stderr_buf) - 1) {
        n = read(pipes.stderr_pipe[0], res->stderr_buf + err_total, sizeof(res->stderr_buf) - err_total - 1);
        if (n > 0) err_total += n;
        else break;
    }

    // 確保字串安全結尾
    res->stdout_buf[out_total] = '\0';
    res->stderr_buf[err_total] = '\0';

    // 關鍵修改：當前階段結束，立刻乾淨關閉讀取端，杜絕 FD 殘留洩漏！
    close(pipes.stdout_pipe[0]);
    close(pipes.stderr_pipe[0]);

    // 解析退出狀態
    // === 替換原本的 status 判斷邏輯 ===
    fprintf(stderr, "\n========================================\n");
    fprintf(stderr, "[Parent DEBUG] 子進程 waitpid 原始狀態碼 status = %d\n", status);
    
    if (WIFEXITED(status)) {
        fprintf(stderr, "[Parent DEBUG] 判定結果：子進程是【自己結束】的 (Normal Exit)\n");
        fprintf(stderr, "[Parent DEBUG] 實際的 Exit Code = %d\n", WEXITSTATUS(status));
        res->exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        fprintf(stderr, "[Parent DEBUG] 判定結果：子進程是被【核心信號轟殺】的 (Signaled)\n");
        fprintf(stderr, "[Parent DEBUG] 殺死它的 Signal 數字 = %d\n", WTERMSIG(status));
        res->exit_code = 128 + WTERMSIG(status);
    } else {
        fprintf(stderr, "[Parent DEBUG] 子進程處於奇特狀態\n");
        res->exit_code = -1;
    }
    fprintf(stderr, "========================================\n\n");

    if (res->stdout_buf[0] != '\0') { fprintf(stderr, "%s", res->stdout_buf); }
    if (res->stderr_buf[0] != '\0') { fprintf(stderr, "%s", res->stderr_buf); }

    return status;
}

int main(int argc, char *argv[]){
    if(argc != 2){
        fprintf(stderr, "Usage: %s <job_id>\n", argv[0]);
        return EXIT_FAILURE;
    }

    current_job_id = argv[1];
    StageResult comp_res = {0};
    StageResult exec_res = {0};

    fprintf(stderr, "\n========== Sandbox ==========\n");
    fprintf(stderr, "[Parent] Managing Job ID: %s\n", current_job_id);

    if(prepare_rootfs(current_job_id) != 0){
        fprintf(stderr, "[Parent] Rootfs preparation failed\n");
        return EXIT_FAILURE;
    }
    //prepare_test_source(current_job_id);
    if(mount_overlayfs(current_job_id) != 0){
        return EXIT_FAILURE;
    }

    int compile_status = run_sandboxed_stage(compile_child_func, "compile", &comp_res);
    if(compile_status == -1 || !WIFEXITED(compile_status) || WEXITSTATUS(compile_status) != 0){
        fprintf(stderr, "[Parent] Compile stage failed\n");
        write_combined_json(current_job_id, &comp_res, &exec_res);
        cleanup_container_filesystem(current_job_id);
        return EXIT_FAILURE;
    }

    fprintf(stderr, "-------------------------------- Compile stage finished ----------------------------------\n");

    int exec_status = run_sandboxed_stage(execute_child_func, "execute", &exec_res);
    write_combined_json(current_job_id, &comp_res, &exec_res);

    if(exec_status == -1){
        cleanup_container_filesystem(current_job_id);
        return EXIT_FAILURE;
    }

    print_sandbox_result(exec_status);
    cleanup_container_filesystem(current_job_id);
    fprintf(stderr, "[Parent] All stages completed successfully.\n");
    
    return EXIT_SUCCESS;
}

/*
char *exec_args[] = {"/bin/sh",NULL};
execve("/bin/sh",exec_args,environ);
perror("execve");
exit(1);
*/