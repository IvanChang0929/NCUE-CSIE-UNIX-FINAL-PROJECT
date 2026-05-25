#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <sys/types.h>


#include "payload.h"
#include "sandbox_seccomp.h"


extern char **environ;
extern char *current_language;

int compile_program(void){

    if(strcmp(current_language, "c") == 0){

        printf("[Sandbox] Compiling C program...\n");

        pid_t pid = fork();

        if(pid == -1){
            perror("fork gcc");
            return -1;
        }

        if(pid == 0){

            char *args[] = {
                "gcc",
                "/app/main.c",
                "-o",
                "/app/user_program",
                NULL
            };

            execvp("gcc", args);

            perror("execvp gcc failed");
            exit(1);
        }

        int status;

        if(waitpid(pid, &status, 0) == -1){
            perror("waitpid gcc");
            return -1;
        }

        if(WIFEXITED(status) && WEXITSTATUS(status) == 0){

            printf("[Sandbox] Compilation successful\n");

            return 0;
        }

        fprintf(stderr, "[Sandbox] Compilation failed\n");

        return -1;
    }

    else if(strcmp(current_language, "python") == 0){

        fprintf(stderr, "[Sandbox] Python does not require compilation\n");

        return 0;
    }

    fprintf(
        stderr,
        "[Sandbox] Unsupported language: %s\n",
        current_language
    );

    return -1;
}

void execute_program(void){

    printf("[Sandbox] Dropping privileges...\n");

    setup_seccomp();

    printf("[Sandbox] Executing user program...\n");

    clearenv();
    setenv("PATH", "/bin:/usr/bin", 1);

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