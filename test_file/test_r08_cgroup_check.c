#include <stdio.h>
#include <string.h>
#include <errno.h>

void print_file(const char *path) {
    FILE *fp = fopen(path, "r");
    char buf[256];

    printf("Checking %s\n", path);

    if (fp == NULL) {
        printf("[WARN] cannot open %s: %s\n", path, strerror(errno));
        return;
    }

    while (fgets(buf, sizeof(buf), fp)) {
        printf("%s", buf);
    }

    fclose(fp);
}

int main() {
    printf("Cgroup visibility check\n\n");

    print_file("/proc/self/cgroup");
    printf("\n");

    print_file("/proc/self/mountinfo");

    printf("\nCgroup check finished.\n");
    return 0;
}