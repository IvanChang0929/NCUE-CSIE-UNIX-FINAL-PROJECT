#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "payload.h"
#include "sandbox_seccomp.h"

extern char **environ;

int compile_program(void){
    fprintf(stderr, "[Sandbox] Compiling user program...\n");

    int status = system("gcc /app/main.c -o /app/user_program 2>&1");

    if(status != 0){
        fprintf(stderr, "[Sandbox] Compilation failed\n");
        return -1;
    }

    fprintf(stderr, "[Sandbox] Compilation successful\n");
    return 0;
}

void execute_program(void){
    fprintf(stderr, "[Sandbox] Dropping privileges...\n");
    setup_seccomp();
    fprintf(stderr, "[Sandbox] Executing user program...\n");

    fflush(stdout);
    fflush(stderr);

    close(stdout_pipe[0]);
    close(stderr_pipe[0]);

    dup2(stdout_pipe[1], STDOUT_FILENO);
    dup2(stderr_pipe[1], STDERR_FILENO);

    close(stdout_pipe[1]);
    close(stderr_pipe[1]);

    char *exec_args[] = {"/app/user_program", NULL};
    execve("/app/user_program", exec_args, environ);

    perror("execve");
    exit(1);
}