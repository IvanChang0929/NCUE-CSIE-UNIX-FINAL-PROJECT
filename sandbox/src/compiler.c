#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>

#include <unistd.h>
#include <sys/wait.h>
#include <sys/stat.h>

#include <fcntl.h>
#include <string.h>
#include <errno.h>

#include "compiler.h"

#define TMP_DIR "./sandbox/tmp"

#define BUILD_DIR "./sandbox/tmp/build"

#define OUTPUT_BINARY "./sandbox/tmp/build/user_program"

extern char **environ;

void prepare_build_directory(){

    if(mkdir(TMP_DIR,0755) == -1 && errno != EEXIST){
        perror("mkdir tmp");
        exit(1);
    }

    if(mkdir(BUILD_DIR,0755) == -1 && errno != EEXIST){
        perror("mkdir build");
        exit(1);
    }

    printf("[Sandbox] Build directory ready\n");
}

void compile_source(char *source_file){

    printf("[Sandbox] Start compile...\n");

    pid_t pid = fork();

    if(pid < 0){
        perror("fork compile");
        exit(1);
    }

    // compile child
    if(pid == 0){

        char *compile_args[] = {
            "gcc",
            source_file,
            "-o",
            OUTPUT_BINARY,
            NULL
        };

        execve(
            "/usr/bin/gcc",
            compile_args,
            environ
        );

        perror("execve gcc");

        exit(1);
    }

    int status;

    waitpid(pid,&status,0);

    if(!WIFEXITED(status) || WEXITSTATUS(status) != 0){
        fprintf(stderr,"[Sandbox] Compile failed\n");
        exit(1);
    }

    printf("[Sandbox] Compile success\n");
}

void execute_program(){

    printf("[Sandbox] Execute user program...\n\n");

    char *exec_args[] = {
        OUTPUT_BINARY,
        NULL
    };

    execve(
        OUTPUT_BINARY,
        exec_args,
        environ
    );

    perror("execve user_program");

    exit(1);
}