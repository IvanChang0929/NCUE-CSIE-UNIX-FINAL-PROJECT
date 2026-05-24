#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

void try_read(const char *path) {
    FILE *fp = fopen(path, "r");

    if (fp == NULL) {
        printf("[OK] cannot read %s: %s\n", path, strerror(errno));
        return;
    }

    printf("[FAIL] can read %s. Host filesystem may be exposed.\n", path);
    fclose(fp);
}

int main() {
    printf("Host filesystem isolation test\n");

    try_read("/etc/shadow");
    try_read("/root/.bashrc");
    try_read("/home/ivanchang/.bashrc");
    try_read("/tmp/sandbox");

    printf("Filesystem isolation check finished.\n");
    return 0;
}