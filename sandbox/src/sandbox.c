#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mount.h>
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <signal.h>

#include "limit.h"
#include "namespace.h"
#include "filesystem.h"
#include "sandbox_seccomp.h"
#include "payload.h"
#include "result_writer.h"


#define TIME_LIMIT_SEC 5
#define STACK_SIZE (1024 * 1024)

typedef struct {
    int stdout_pipe[2];
    int stderr_pipe[2];
} ChildPipeArgs;

static char child_stack[STACK_SIZE];
static int sync_pipe[2];
char *current_job_id = NULL;
char *current_language = NULL;

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
        "#include <stdio.h>\n\n"
        "int main() {\n"
        "    while(1){\n"
        "        printf(\"AAAAAAAAAAAAAAAAAAAA\\n\");\n"
        "    }\n"
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
    if(read(sync_pipe[0], &buf, 1) == -1){
        exit(1);
    }

    if(setgid(0) == -1){
        perror("setgid failed");
        exit(1);
    }
    if(setuid(0) == -1){
        perror("setuid failed");
        exit(1);
    }

    setup_mount_namespace();
    setup_pivot_root(current_job_id);
    setup_resource_limits();

    pid_t pid2 = fork();
    if(pid2 == -1){
        perror("fork payload failed");
        exit(1);
    }
    if(pid2 == 0){
        sigset_t mask;
        sigemptyset(&mask);
        if (sigprocmask(SIG_SETMASK, &mask, NULL) == -1) {
            perror("sigprocmask failed");
        }

        for (int i = 1; i < NSIG; i++) {
            signal(i, SIG_DFL);
        }

        redirect_execute_output(pipes->stderr_pipe);

        for(int i = 3; i < 32; i++){
            if(i != STDOUT_FILENO && i != STDERR_FILENO){
                close(i);
            }
        }

        if (setgid(1000) == -1) { perror("setgid failed"); exit(1); }
        if (setuid(1000) == -1) { perror("setuid failed"); exit(1); }

        execute_program();

        perror("execute_program failed");
        exit(1);

    }else{
        close(pipes->stdout_pipe[0]);
        close(pipes->stdout_pipe[1]);
        close(pipes->stderr_pipe[0]);
        close(pipes->stderr_pipe[1]);

        int status;
        
        if(waitpid(pid2, &status, 0) == -1){
            perror("waitpid in init");
            exit(1);
        }

        if(WIFSIGNALED(status)){
            exit(128 + WTERMSIG(status));
        }
        
        // 若為正常結束，直接回傳 PID 2 的退出碼
        exit(WEXITSTATUS(status));
    }
}

int run_sandboxed_stage(int (*child_func)(void *), const char *stage_name, StageResult *res) {
    res->executed = 1;
    ChildPipeArgs pipes;

    if (pipe(sync_pipe) == -1 || pipe(pipes.stdout_pipe) == -1 || pipe(pipes.stderr_pipe) == -1) {
        perror("pipe creation failed");
        return -1;
    }

    int clone_flags = CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER | SIGCHLD;
    pid_t pid = clone(child_func, child_stack + STACK_SIZE, clone_flags, &pipes);

    if (pid == -1) {
        fprintf(stderr, "[Parent] clone %s failed\n", stage_name);
        return -1;
    }

    close(sync_pipe[0]);
    close(pipes.stdout_pipe[1]);
    close(pipes.stderr_pipe[1]);

    setup_uid_gid_map(pid);
    setup_cgroup(pid);

    if (write(sync_pipe[1], "x", 1) == -1) {
        perror("write sync_pipe");
        return -1;
    }
    close(sync_pipe[1]);

    fcntl(pipes.stdout_pipe[0], F_SETFL, fcntl(pipes.stdout_pipe[0], F_GETFL) | O_NONBLOCK);
    fcntl(pipes.stderr_pipe[0], F_SETFL, fcntl(pipes.stderr_pipe[0], F_GETFL) | O_NONBLOCK);

    int status = 0;
    size_t out_total = 0;
    size_t err_total = 0;
    ssize_t n;
    
    // ▼ 新增：用來記錄是否因為超時而被外層砍掉
    int is_timeout = 0; 

    struct rusage usage; 
    memset(&usage, 0, sizeof(usage));

    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);

    while (1) {
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

        pid_t ret = wait4(pid, &status, WNOHANG, &usage);
        if (ret == pid) break; 
        if (ret == -1) {
            if (errno == EINTR) continue;
            perror("wait4");
            return -1;
        }

        clock_gettime(CLOCK_MONOTONIC, &now);
        double elapsed = (now.tv_sec - start.tv_sec) + (now.tv_nsec - start.tv_nsec) / 1e9;

        if (elapsed > TIME_LIMIT_SEC) {
            fprintf(stderr, "\n[Parent] Time Limit Exceeded (Wall-clock timeout)\n");
            kill(pid, SIGKILL); 
            
            // ▼ 標記超時發生
            is_timeout = 1; 
            
            wait4(pid, &status, 0, &usage);
            break;
        }

        usleep(10000); 
    }

    // 收尾：讀取剩下的輸出
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

    res->stdout_buf[out_total] = '\0';
    res->stderr_buf[err_total] = '\0';
    close(pipes.stdout_pipe[0]);
    close(pipes.stderr_pipe[0]);

    long user_ms = (usage.ru_utime.tv_sec * 1000) + (usage.ru_utime.tv_usec / 1000);
    long sys_ms  = (usage.ru_stime.tv_sec * 1000) + (usage.ru_stime.tv_usec / 1000);
    
    res->time_ms = user_ms + sys_ms;  
    res->memory_kb = usage.ru_maxrss; 

    fprintf(stderr, "\n========================================\n");
    fprintf(stderr, "[Parent DEBUG] 子進程 wait4 原始狀態碼 status = %d\n", status);
    fprintf(stderr, "[Parent DEBUG] 消耗時間: %ld ms, 記憶體: %ld KB\n", res->time_ms, res->memory_kb);

    if(WIFEXITED(status)){
        int ext_code = WEXITSTATUS(status);
        
        if (ext_code > 128) {
            int sig = ext_code - 128;
            fprintf(stderr, "[Parent DEBUG] 判定結果：被 PID 1 代理回報信號轟殺 (Translated Signal)\n");
            fprintf(stderr, "[Parent DEBUG] 殺死 PID 2 的 Signal 數字 = %d\n", sig);

            if(sig == SIGXFSZ){
                fprintf(stderr, "[Parent] Output Limit Exceeded (SIGXFSZ)\n");
                res->exit_code = 153;
                snprintf(res->status_message, sizeof(res->status_message), "Output Limit Exceeded (SIGXFSZ)");
            }
            else if(sig == SIGKILL){
                fprintf(stderr, "[Parent] Process Killed (SIGKILL)\n");
                res->exit_code = 137;
                snprintf(res->status_message, sizeof(res->status_message), "Process Killed (SIGKILL)");
            }
            else if(sig == SIGSEGV){
                fprintf(stderr, "[Parent] Segmentation Fault\n");
                res->exit_code = 139;
                snprintf(res->status_message, sizeof(res->status_message), "Segmentation Fault");
            }
            else if(sig == SIGFPE){
                fprintf(stderr, "[Parent] Floating Point Exception\n");
                res->exit_code = 136;
                snprintf(res->status_message, sizeof(res->status_message), "Floating Point Exception");
            }
            else if(sig == SIGABRT){
                fprintf(stderr, "[Parent] Abort Signal\n");
                res->exit_code = 134;
                snprintf(res->status_message, sizeof(res->status_message), "Abort Signal");
            }
            else if(sig == SIGSYS){
                fprintf(stderr, "[Parent] Seccomp Blocked Syscall\n");
                res->exit_code = 159;
                snprintf(res->status_message, sizeof(res->status_message), "Seccomp Blocked Syscall");
            }
            else{
                res->exit_code = 128 + sig;
                snprintf(res->status_message, sizeof(res->status_message), "Killed by Signal %d", sig);
            }
        }else{
            fprintf(stderr, "[Parent DEBUG] 判定結果：子進程是【自己結束】的 (Normal Exit)\n");
            fprintf(stderr, "[Parent DEBUG] 實際的 Exit Code = %d\n", ext_code);
            res->exit_code = ext_code;
        }
    } else if(WIFSIGNALED(status)){

        int sig = WTERMSIG(status);

        fprintf(stderr,
            "[Parent DEBUG] 判定結果：子進程是被【核心信號轟殺】的 (Signaled)\n");

        fprintf(stderr,
            "[Parent DEBUG] 殺死它的 Signal 數字 = %d\n",
            sig);

        // ==============================
        // ▼ 針對 Timeout 被外層殺死，或者是 OOM 觸發的精準特判
        // ==============================

        if(sig == SIGXFSZ){
            fprintf(stderr, "[Parent] Output Limit Exceeded (SIGXFSZ)\n");
            res->exit_code = 153;
            snprintf(res->status_message, sizeof(res->status_message), "Output Limit Exceeded (SIGXFSZ)");
        }
        else if(sig == SIGKILL){
            // ▼ 透過旗標分流：時間超時 (TLE) 或是 記憶體爆掉 (MLE/OOM)
            if (is_timeout) {
                fprintf(stderr, "[Parent] Time Limit Exceeded (TLE)\n");
                res->exit_code = 137;
                snprintf(res->status_message, sizeof(res->status_message), "Time Limit Exceeded (TLE)");
            } else {
                fprintf(stderr, "[Parent] Process Killed (OOM / MLE)\n");
                res->exit_code = 137;
                snprintf(res->status_message, sizeof(res->status_message), "Process Killed (OOM / MLE)");
            }
        }
        else if(sig == SIGSEGV){
            fprintf(stderr, "[Parent] Segmentation Fault\n");
            res->exit_code = 139;
            snprintf(res->status_message, sizeof(res->status_message), "Segmentation Fault");
        }
        else if(sig == SIGFPE){
            fprintf(stderr, "[Parent] Floating Point Exception\n");
            res->exit_code = 136;
            snprintf(res->status_message, sizeof(res->status_message), "Floating Point Exception");
        }
        else if(sig == SIGABRT){
            fprintf(stderr, "[Parent] Abort Signal\n");
            res->exit_code = 134;
            snprintf(res->status_message, sizeof(res->status_message), "Abort Signal");
        }
        else if(sig == SIGSYS){
            fprintf(stderr, "[Parent] Seccomp Blocked Syscall\n");
            res->exit_code = 159;
            snprintf(res->status_message, sizeof(res->status_message), "Seccomp Blocked Syscall");
        }
        else{
            res->exit_code = 128 + sig;
            snprintf(res->status_message, sizeof(res->status_message), "Killed by Signal %d", sig);
        }
    }
    else {
        fprintf(stderr, "[Parent DEBUG] 子進程處於奇特狀態\n");
        res->exit_code = -1;
    }
    fprintf(stderr, "========================================\n\n");

    if (res->stdout_buf[0] != '\0') fprintf(stderr, "%s", res->stdout_buf);
    if (res->stderr_buf[0] != '\0') fprintf(stderr, "%s", res->stderr_buf);

    return status;
}

int main(int argc, char *argv[]){
    if(argc != 3){
        fprintf(stderr, "Usage: %s <job_id> <language>\n", argv[0]);
        return EXIT_FAILURE;
    }

    current_job_id = argv[1];
    current_language = argv[2];
    StageResult comp_res = {0};
    StageResult exec_res = {0};

    fprintf(stderr, "\n========== Sandbox ==========\n");
    fprintf(stderr, "[Parent] Managing Job ID: %s\n", current_job_id);

    if(prepare_rootfs(current_job_id) != 0){
        fprintf(stderr, "[Parent] Rootfs preparation failed\n");
        return EXIT_FAILURE;
    }
    prepare_test_source(current_job_id);
    if(mount_overlayfs(current_job_id,current_language) != 0){
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