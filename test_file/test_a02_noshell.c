#include <stdio.h>
#include <unistd.h>

extern char **environ;

int main() {
    printf("=== Shell Existence Test ===\n");

    char *args[] = {"/bin/sh", NULL};

    execve("/bin/sh", args, environ);

    perror("execve");

    return 0;
}