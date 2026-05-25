#include <stdio.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <string.h>

int main() {
    struct stat st;

    printf("Root filesystem escape test\n");

    if (stat("/", &st) == 0) {
        printf("[OK] sandbox root exists: /\n");
    } else {
        printf("[FAIL] cannot stat /: %s\n", strerror(errno));
        return 1;
    }

    if (stat("/oldroot", &st) == -1) {
        printf("[OK] /oldroot does not exist. Old root is not visible.\n");
    } else {
        printf("[FAIL] /oldroot is visible. Possible pivot_root cleanup issue.\n");
        return 1;
    }

    if (stat("/tmp/sandbox", &st) == -1) {
        printf("[OK] host /tmp/sandbox is not visible inside container.\n");
    } else {
        printf("[WARN] /tmp/sandbox is visible. Check rootfs isolation.\n");
    }

    printf("Root isolation check finished.\n");
    return 0;
}