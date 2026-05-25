#include <stdio.h>
#include <stdlib.h>

extern char **environ;

int main() {

    printf("=== ENV TEST ===\n");

    for(char **env = environ; *env != NULL; env++) {
        printf("%s\n", *env);
    }

    return 0;
}