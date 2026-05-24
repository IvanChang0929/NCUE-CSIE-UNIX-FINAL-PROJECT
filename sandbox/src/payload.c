#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#include "payload.h"
#include "sandbox_seccomp.h"

extern char **environ;
extern char *current_language;

int compile_program(void){
    if(strcmp(current_language, "c") == 0){
        fprintf(stderr,
            "[Sandbox] Compiling C program...\n");
        int status = system(
            "gcc /app/main.c -o /app/user_program"
        );

        if(status != 0){
            fprintf(stderr,
                "[Sandbox] Compilation failed\n");

            return -1;
        }

        fprintf(stderr,
            "[Sandbox] Compilation successful\n");

        return 0;
    }else if(strcmp(current_language, "python") == 0){
        fprintf(stderr,
            "[Sandbox] Python does not require compilation\n");

        return 0;
    }
    fprintf(stderr,
        "[Sandbox] Unsupported language: %s\n",
        current_language
    );

    return -1;
}

void execute_program(void){

    fprintf(stderr,
        "[Sandbox] Dropping privileges...\n");

    setup_seccomp();

    fprintf(stderr,
        "[Sandbox] Executing user program...\n");

    if(strcmp(current_language, "c") == 0){

        char *exec_args[] = {
            "/app/user_program",
            NULL
        };
        execve(
            "/app/user_program",
            exec_args,
            environ
        );
    }else if(strcmp(current_language, "python") == 0){

        char *exec_args[] = {
            "/usr/bin/python3",
            "/app/main.py",
            NULL
        };

        execve(
            "/usr/bin/python3",
            exec_args,
            environ
        );
    }

    perror("execve");

    exit(1);
}