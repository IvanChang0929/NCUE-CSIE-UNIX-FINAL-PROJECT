#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>

#include <sched.h>
#include <unistd.h>

#include <sys/wait.h>

#include "compiler.h"
#include "limit.h"
#include "namespace.h"

#define STACK_SIZE (1024 * 1024)

static char child_stack[STACK_SIZE];
static int sync_pipe[2];

int child_func(void *arg){
    close(sync_pipe[1]);
    char buf;
    if(read(sync_pipe[0], &buf, 1) == -1){
        perror("read sync_pipe");
        exit(1);
    }

    char *source_file = (char *)arg;

    printf("[Sandbox] PID = %d\n", getpid());
    printf("[Sandbox] PPID = %d\n", getppid());
    
    setup_mount_namespace();

    setup_resource_limits();

    prepare_build_directory();

    compile_source(source_file);

    execute_program();

    return 0;
}

int main(int argc, char *argv[]){

    if(argc != 2){
        fprintf(stderr,"Usage: %s <source_file>\n",argv[0]);
        return 1;
    }

    char *source_file = argv[1];

    printf("\n========== Sandbox ==========\n");
    printf("Source: %s\n", source_file);
    printf("=============================\n");

    printf("[Parent] PID = %d\n\n", getpid());

    if(pipe(sync_pipe) == -1){
        perror("pipe");
        return 1;
    }

    pid_t pid = clone(child_func,child_stack + STACK_SIZE,
        CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER | SIGCHLD,
        source_file
    );

    if(pid == -1){
        perror("clone");
        return 1;
    }

    close(sync_pipe[0]);
    setup_uid_gid_map(pid);
    if(write(sync_pipe[1], "x", 1) == -1){
        perror("write sync_pipe");
        return 1;
    }

    int status;

    waitpid(pid, &status, 0);

    printf("\n========== Result ==========\n");

    if(WIFEXITED(status)){
        printf("[Parent] Exit Code = %d\n",WEXITSTATUS(status));
    }else if(WIFSIGNALED(status)){
        printf("[Parent] Killed By Signal = %d\n",WTERMSIG(status));
    }

    printf("============================\n");

    return 0;
}


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