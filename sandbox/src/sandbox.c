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

static char child_stack[STACK_SIZE];
static int sync_pipe[2];
int stdout_pipe[2];
int stderr_pipe[2];
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
        "int main() {\n"
        "    printf(\"Hello from Job %s!\\n\");\n"
        "    return 0;\n"
        "}\n",
        job_id
    );
    fclose(fp);

    fprintf(stderr, "[Parent] Default test source prepared: %s\n", source_path);
}

static void redirect_stage_output(void){
    fflush(stdout);
    fflush(stderr);

    close(stdout_pipe[0]);
    close(stderr_pipe[0]);

    dup2(stdout_pipe[1], STDOUT_FILENO);
    dup2(stderr_pipe[1], STDERR_FILENO);

    close(stdout_pipe[1]);
    close(stderr_pipe[1]);
}

int compile_child_func(void *arg){
    (void)arg;
    close(sync_pipe[1]);

    char buf;
    if(read(sync_pipe[0], &buf, 1) == -1){
        perror("read sync_pipe");
        exit(1);
    }

    setup_mount_namespace();
    setup_pivot_root(current_job_id);
    setup_resource_limits();
    setup_seccomp();
    redirect_stage_output();
    if(compile_program() != 0){
        exit(1);
    }
    return 0;
}

int execute_child_func(void *arg){
    (void)arg;
    close(sync_pipe[1]);

    char buf;
    if(read(sync_pipe[0], &buf, 1) == -1){
        perror("read sync_pipe");
        exit(1);
    }

    setup_mount_namespace();
    setup_pivot_root(current_job_id);
    setup_resource_limits();
    redirect_stage_output();
    execute_program();

    return 0;
}

int run_sandboxed_stage(int (*child_func)(void *),const char *stage_name,StageResult *res){
    res->executed = 1;
    if (pipe(sync_pipe) == -1 || pipe(stdout_pipe) == -1 || pipe(stderr_pipe) == -1) {
        perror("pipe creation failed");
        return -1;
    }

    int clone_flags = CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER | SIGCHLD;
    pid_t pid = clone(child_func, child_stack + STACK_SIZE, clone_flags, NULL);

    if (pid == -1) {
        fprintf(stderr, "[Parent] clone %s failed\n", stage_name);
        return -1;
    }

    close(sync_pipe[0]);    // 父進程不讀同步訊號
    close(stdout_pipe[1]);  // 父進程不寫標準輸出
    close(stderr_pipe[1]);  // 父進程不寫標準錯誤

    setup_uid_gid_map(pid);
    setup_cgroup(pid);

    if (write(sync_pipe[1], "x", 1) == -1) {
        perror("write sync_pipe");
        return -1;
    }
    close(sync_pipe[1]);

    fcntl(stdout_pipe[0], F_SETFL, fcntl(stdout_pipe[0], F_GETFL) | O_NONBLOCK);
    fcntl(stderr_pipe[0], F_SETFL, fcntl(stderr_pipe[0], F_GETFL) | O_NONBLOCK);

    int status;
    int elapsed = 0;
    size_t out_total = 0;
    size_t err_total = 0;
    ssize_t n;

    while (1) {
        // --- 邊等邊讀：持續抽乾 Pipe，避免子進程被 IO 阻塞 ---
        
        // 嘗試讀取 stdout
        while (out_total < sizeof(res->stdout_buf) - 1) {
            n = read(stdout_pipe[0], res->stdout_buf + out_total, sizeof(res->stdout_buf) - out_total - 1);
            if (n > 0) out_total += n;
            else break; // 讀空了或發生 EAGAIN
        }

        // 嘗試讀取 stderr
        while (err_total < sizeof(res->stderr_buf) - 1) {
            n = read(stderr_pipe[0], res->stderr_buf + err_total, sizeof(res->stderr_buf) - err_total - 1);
            if (n > 0) err_total += n;
            else break; // 讀空了或發生 EAGAIN
        }

        // 檢查子進程狀態
        pid_t ret = waitpid(pid, &status, WNOHANG);
        if (ret == pid) {
            break; // 子進程結束
        }
        if (ret == -1) {
            perror("waitpid");
            return -1;
        }

        /*
        // Timeout 處理機制
        // 注意：因為下面改用 usleep(100000) 也就是 0.1 秒
        // 所以 5 秒的 Timeout 條件要改成 elapsed >= 50
        if (elapsed >= 50) {
            fprintf(stderr, "[Parent] Stage %s timeout\n", stage_name);
            kill(pid, SIGKILL);
            waitpid(pid, &status, 0); // 回收殭屍進程
            
            res->exit_code = 124;
            snprintf(res->stderr_buf, sizeof(res->stderr_buf), "TIMEOUT");
            
            close(stdout_pipe[0]);
            close(stderr_pipe[0]);
            return status;
        }
        */

        // 用 0.1 秒取代 1 秒，讓讀取更即時，減少 Pipe 滿載的機會
        usleep(100000); 
        elapsed++;
    }

    while (out_total < sizeof(res->stdout_buf) - 1) {
        n = read(stdout_pipe[0], res->stdout_buf + out_total, sizeof(res->stdout_buf) - out_total - 1);
        if (n > 0) out_total += n;
        else break;
    }
    while (err_total < sizeof(res->stderr_buf) - 1) {
        n = read(stderr_pipe[0], res->stderr_buf + err_total, sizeof(res->stderr_buf) - err_total - 1);
        if (n > 0) err_total += n;
        else break;
    }

    // 確保字串有結尾符號
    res->stdout_buf[out_total] = '\0';
    res->stderr_buf[err_total] = '\0';

    close(stdout_pipe[0]);
    close(stderr_pipe[0]);

    if (WIFEXITED(status)) {
        res->exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        res->exit_code = 128 + WTERMSIG(status);
    } else {
        res->exit_code = -1;
    }

    if (res->stdout_buf[0] != '\0') {
        fprintf(stderr, "%s", res->stdout_buf);
    }
    if (res->stderr_buf[0] != '\0') {
        fprintf(stderr, "%s", res->stderr_buf);
    }

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
    prepare_test_source(current_job_id);
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