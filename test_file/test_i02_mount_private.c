#include <stdio.h>
#include <string.h>

int main() {
    FILE *fp;
    char line[1024];
    int suspicious_shared = 0;

    printf("Mount propagation check\n");

    fp = fopen("/proc/self/mountinfo", "r");
    if (fp == NULL) {
        perror("open /proc/self/mountinfo");
        return 1;
    }

    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, " shared:") != NULL) {
            suspicious_shared = 1;
            printf("[WARN] shared mount found:\n%s", line);
        }
    }

    fclose(fp);

    if (!suspicious_shared) {
        printf("[OK] no shared propagation tag found in mountinfo.\n");
    } else {
        printf("[WARN] some mounts are shared. Check MS_PRIVATE setup.\n");
    }

    return 0;
}