#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>

#include <sched.h>
#include <unistd.h>

#include <sys/wait.h>
#include <sys/resource.h>
#include <sys/mount.h>
#include <sys/stat.h>

#include <fcntl.h>
#include <string.h>
#include <signal.h>
#include <errno.h>

#define STACK_SIZE (1024 * 1024)

#define MEMORY_LIMIT (128 * 1024 * 1024)
#define CPU_LIMIT 2

static char child_stack[STACK_SIZE];

extern char **environ;

int child_func(void *arg){

    char *source_file = (char *)arg;

    printf("[Namespace Child] PID = %d\n", getpid());
    printf("[Namespace Child] PPID = %d\n", getppid());

    if(mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) == -1){
        perror("mount MS_PRIVATE");
        exit(1);
    }
    printf("[Namespace Child] Mount propagation isolated\n");

    if(mount("proc", "/proc", "proc", 0, NULL) == -1){
        perror("mount proc");
    }
    printf("[Namespace Child] Mount Namespace: /proc remounted\n");

    // =====================================
    // TODO
    // =====================================

    // chroot / pivot_root
    // seccomp
    // cgroup
    // capability drop

    // =====================================
    // Resource Limits
    // =====================================

    struct rlimit cpu_limit;

    cpu_limit.rlim_cur = CPU_LIMIT;
    cpu_limit.rlim_max = CPU_LIMIT;

    if(setrlimit(RLIMIT_CPU, &cpu_limit) == -1){
        perror("setrlimit CPU");
        exit(1);
    }

    struct rlimit mem_limit;

    mem_limit.rlim_cur = MEMORY_LIMIT;
    mem_limit.rlim_max = MEMORY_LIMIT;

    if(setrlimit(RLIMIT_AS, &mem_limit) == -1){
        perror("setrlimit MEM");
        exit(1);
    }

    printf("[Namespace Child] Resource limits applied\n");


    if(mkdir("/tmp/build", 0755) == -1 && errno != EEXIST){
        perror("mkdir /tmp/build");
        exit(1);
    }
    printf("[Namespace Child] Build directory ready\n");


    printf("[Namespace Child] Start compile...\n");
    pid_t compile_pid = fork();

    if(compile_pid < 0){
        perror("fork compile");
        exit(1);
    }

    if(compile_pid == 0){
        char *compile_args[] = {
            "gcc",
            source_file,
            "-o",
            "/tmp/build/user_program",
            NULL
        };

        execve("/usr/bin/gcc",
               compile_args,
               environ);

        perror("execve gcc");
        exit(1);
    }

    int compile_status;

    waitpid(compile_pid, &compile_status, 0);

    if(!WIFEXITED(compile_status) || WEXITSTATUS(compile_status) != 0){
        fprintf(stderr,
                "[Namespace Child] Compile failed\n");
        exit(1);
    }

    printf("[Namespace Child] Compile success\n");


    printf("[Namespace Child] Execute user program...\n\n");
    char *exec_args[] = {
        "/tmp/build/user_program",
        NULL
    };

    execve("/tmp/build/user_program",
           exec_args,
           environ);

    perror("execve user_program");

    return 1;
}

int main(int argc, char *argv[]){

    if(argc != 2){
        fprintf(stderr,
                "Usage: %s <source_file>\n",
                argv[0]);

        return 1;
    }

    char *source_file = argv[1];

    printf("\n========== Sandbox ==========\n");

    printf("Source: %s\n", source_file);

    printf("=============================\n");

    printf("[Parent] PID = %d\n\n", getpid());

    pid_t pid = clone(
        child_func,
        child_stack + STACK_SIZE,

        CLONE_NEWPID |
        CLONE_NEWNS |
        SIGCHLD,

        source_file
    );

    if(pid == -1){
        perror("clone");
        return 1;
    }

    int status;

    waitpid(pid, &status, 0);

    printf("\n========== Result ==========\n");

    if(WIFEXITED(status)){

        printf("[Parent] Exit Code = %d\n",
               WEXITSTATUS(status));
    }
    else if(WIFSIGNALED(status)){

        printf("[Parent] Killed By Signal = %d\n",
               WTERMSIG(status));
    }

    printf("============================\n");

    return 0;
}