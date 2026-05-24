#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>

#include <sys/resource.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <sys/stat.h>

#include "limit.h"
#include <fcntl.h>
#include <errno.h>

#define CPU_LIMIT          3
#define MEMORY_LIMIT       (256 * 1024 * 1024)
#define NPROC_LIMIT        16
#define NOFILE_LIMIT       32
#define FILESIZE_LIMIT     (1 * 1024 * 1024)

#define CGROUP_BASE_PATH "/sys/fs/cgroup"

static void set_limit(int resource, rlim_t soft,rlim_t hard){
    struct rlimit rl = {soft, hard};
    if(setrlimit(resource, &rl) == -1){
        perror("setrlimit");
        exit(1);
    }
}

static void build_cgroup_path(const char *job_id, char *path, size_t size)
{
    snprintf(path, size, "%s/sandbox_job_%s", CGROUP_BASE_PATH, job_id);
}

static void write_cgroup_file(const char *job_id, const char *name, const char *value)
{
    char cgroup_path[256];
    char path[512];

    build_cgroup_path(job_id, cgroup_path, sizeof(cgroup_path));
    snprintf(path, sizeof(path), "%s/%s", cgroup_path, name);

    int fd = open(path, O_WRONLY);

    if (fd == -1) {
        perror(path);
        exit(1);
    }

    if (write(fd, value, strlen(value)) == -1) {
        perror("write");
        close(fd);
        exit(1);
    }

    close(fd);
}

void setup_resource_limits(long memory_mb, int timeout_sec)
{
    rlim_t memory_bytes = (rlim_t)memory_mb * 1024 * 1024;

    // CPU time limit，這裡用 timeout 當 CPU time 的保護線
    set_limit(RLIMIT_CPU, timeout_sec, timeout_sec + 1);

    // Virtual memory limit
    set_limit(RLIMIT_AS, memory_bytes, memory_bytes);

    // File descriptor limit
    set_limit(RLIMIT_NOFILE, NOFILE_LIMIT, NOFILE_LIMIT);

    // Process limit
    set_limit(RLIMIT_NPROC, NPROC_LIMIT, NPROC_LIMIT);

    // Output file size limit
    set_limit(RLIMIT_FSIZE, FILESIZE_LIMIT, FILESIZE_LIMIT);

    printf("[Sandbox] Resource limits applied\n");
}

static void build_cpu_max_value(double cpu_core, char *buffer, size_t size)
{
    long period = 100000;
    long quota = (long)(cpu_core * period);

    if (quota < 1000) {
        quota = 1000;
    }

    snprintf(buffer, size, "%ld %ld", quota, period);
}

void setup_cgroup(pid_t pid, const char *job_id, double cpu_core, long memory_mb)
{
    char pid_str[32];
    char cgroup_path[256];
    char cpu_max_value[64];
    char memory_max_value[64];

    build_cgroup_path(job_id, cgroup_path, sizeof(cgroup_path));

    if (mkdir(cgroup_path, 0755) == -1) {
        if (errno != EEXIST) {
            perror("mkdir job cgroup");
            exit(1);
        }
    }

    build_cpu_max_value(cpu_core, cpu_max_value, sizeof(cpu_max_value));
    snprintf(memory_max_value, sizeof(memory_max_value), "%ld", memory_mb * 1024 * 1024);

    write_cgroup_file(job_id, "cpu.max", cpu_max_value);
    write_cgroup_file(job_id, "memory.max", memory_max_value);
    write_cgroup_file(job_id, "pids.max", "64");

    snprintf(pid_str, sizeof(pid_str), "%d", pid);
    write_cgroup_file(job_id, "cgroup.procs", pid_str);

    printf(
        "[Parent] cgroup configured for Job %s: CPU %.2f core, Memory %ld MB\n",
        job_id,
        cpu_core,
        memory_mb
    );
}

void print_resource_usage(void){

    struct rusage usage;

    if(getrusage(RUSAGE_CHILDREN, &usage) == -1){
        perror("getrusage");
        return;
    }

    printf("\n========== Resource Usage ==========\n");

    printf(
        "User CPU Time : %ld.%06ld sec\n",
        usage.ru_utime.tv_sec,
        usage.ru_utime.tv_usec
    );

    printf(
        "System CPU Time : %ld.%06ld sec\n",
        usage.ru_stime.tv_sec,
        usage.ru_stime.tv_usec
    );

    printf(
        "Max RSS : %ld KB\n",
        usage.ru_maxrss
    );

    printf(
        "Page Faults : %ld\n",
        usage.ru_majflt
    );

    printf(
        "Context Switches : %ld\n",
        usage.ru_nvcsw + usage.ru_nivcsw
    );

}

void print_sandbox_result(int status){

    printf("\n========== Sandbox Result ==========\n");

    if(WIFEXITED(status)){

        printf(
            "[Parent] Exit Code : %d\n",
            WEXITSTATUS(status)
        );

    }else if(WIFSIGNALED(status)){

        int sig = WTERMSIG(status);

        if(sig == SIGXCPU){

            printf(
                "[Parent] CPU limit exceeded\n"
            );

        }else if(sig == SIGSEGV){

            printf(
                "[Parent] Segmentation fault\n"
            );

        }else if(sig == SIGKILL){

            printf(
                "[Parent] Process killed "
                "(OOM or forced kill)\n"
            );

        }else if(sig == SIGSYS){

            printf(
                "[Parent] Blocked by seccomp\n"
            );

        }else{

            printf(
                "[Parent] Killed by signal : %d\n",
                sig
            );
        }
    }

    print_resource_usage();
}

long read_cgroup_memory_current_kb(const char *job_id)
{
    char cgroup_path[256];
    char memory_path[512];

    build_cgroup_path(job_id, cgroup_path, sizeof(cgroup_path));
    snprintf(memory_path, sizeof(memory_path), "%s/memory.current", cgroup_path);

    FILE *fp = fopen(memory_path, "r");
    if (fp == NULL) {
        return -1;
    }

    long bytes = 0;

    if (fscanf(fp, "%ld", &bytes) != 1) {
        fclose(fp);
        return -1;
    }

    fclose(fp);

    return bytes / 1024;
}

long read_cgroup_cpu_usage_usec(const char *job_id)
{
    char cgroup_path[256];
    char cpu_path[512];

    build_cgroup_path(job_id, cgroup_path, sizeof(cgroup_path));
    snprintf(cpu_path, sizeof(cpu_path), "%s/cpu.stat", cgroup_path);

    FILE *fp = fopen(cpu_path, "r");
    if (fp == NULL) {
        return -1;
    }

    char key[64];
    long value;

    while (fscanf(fp, "%63s %ld", key, &value) == 2) {
        if (strcmp(key, "usage_usec") == 0) {
            fclose(fp);
            return value;
        }
    }

    fclose(fp);
    return -1;
}