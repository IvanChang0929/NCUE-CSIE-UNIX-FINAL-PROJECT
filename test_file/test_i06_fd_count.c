#include <stdio.h>
#include <dirent.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main() {
    DIR *dir;
    struct dirent *entry;
    int count = 0;

    printf("File descriptor inheritance check\n");

    dir = opendir("/proc/self/fd");
    if (dir == NULL) {
        perror("opendir /proc/self/fd");
        return 1;
    }

    printf("Open file descriptors:\n");

    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') {
            continue;
        }

        printf("fd: %s\n", entry->d_name);
        count++;
    }

    closedir(dir);

    printf("Total fd count: %d\n", count);

    if (count <= 5) {
        printf("[OK] fd count is low. No obvious inherited fd leak.\n");
    } else {
        printf("[WARN] fd count is high. Check whether parent pipes or files leaked.\n");
    }

    return 0;
}