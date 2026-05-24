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


#define CGROUP_PATH "/sys/fs/cgroup/sandbox"

static void set_limit(int resource, rlim_t soft,rlim_t hard){
    struct rlimit rl = {soft, hard};
    if(setrlimit(resource, &rl) == -1){
        perror("setrlimit");
        exit(1);
    }
}

static void write_cgroup_file(const char *name,const char *value){

    char path[256];

    snprintf(path,sizeof(path),"%s/%s",CGROUP_PATH,name);

    int fd = open(path, O_WRONLY);

    if(fd == -1){
        perror(path);
        exit(1);
    }

    if(write(fd, value, strlen(value)) == -1){
        perror("write");
        close(fd);
        exit(1);
    }

    close(fd);
}

void setup_resource_limits(){

    // CPU time limit
    set_limit(RLIMIT_CPU,CPU_LIMIT,CPU_LIMIT+1);

    // Virtual memory limit
    set_limit(RLIMIT_AS,MEMORY_LIMIT,MEMORY_LIMIT);

    // File descriptor limit
    set_limit(RLIMIT_NOFILE,NOFILE_LIMIT,NOFILE_LIMIT);

    set_limit(RLIMIT_NPROC,NPROC_LIMIT,NPROC_LIMIT);

    set_limit(RLIMIT_FSIZE,FILESIZE_LIMIT,FILESIZE_LIMIT);

    printf("[Sandbox] Resource limits applied\n");
}

void setup_cgroup(pid_t pid){

    char pid_str[32];

    if(mkdir(CGROUP_PATH, 0755) == -1){
        if(errno != EEXIST){
            perror("mkdir cgroup");
            exit(1);
        }
    }

    write_cgroup_file("cpu.max","50000 100000");

    write_cgroup_file("memory.max","536870912");

    write_cgroup_file("pids.max","64");

    snprintf(pid_str,sizeof(pid_str),"%d",pid);

    write_cgroup_file("cgroup.procs",pid_str);

    printf("[Parent] cgroup configured\n");
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