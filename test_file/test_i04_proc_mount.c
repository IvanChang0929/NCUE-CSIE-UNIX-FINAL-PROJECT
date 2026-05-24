#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>

int main() {
    FILE *fp;
    char line[512];
    int found_proc = 0;

    printf("/proc mount check\n");

    fp = fopen("/proc/mounts", "r");
    if (fp == NULL) {
        printf("[FAIL] cannot open /proc/mounts: %s\n", strerror(errno));
        return 1;
    }

    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, " /proc ") != NULL) {
            found_proc = 1;
            printf("[OK] found /proc mount:\n%s", line);
            break;
        }
    }

    fclose(fp);

    if (!found_proc) {
        printf("[FAIL] /proc is not mounted.\n");
        return 1;
    }

    fp = fopen("/proc/self/status", "r");
    if (fp == NULL) {
        printf("[FAIL] cannot read /proc/self/status: %s\n", strerror(errno));
        return 1;
    }

    printf("[OK] /proc/self/status is readable.\n");
    fclose(fp);

    return 0;
}