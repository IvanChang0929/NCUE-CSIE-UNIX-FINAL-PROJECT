#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>

int main() {
    uid_t uid = getuid();
    uid_t euid = geteuid();
    gid_t gid = getgid();
    gid_t egid = getegid();

    printf("UID/GID privilege check\n");
    printf("uid  = %d\n", uid);
    printf("euid = %d\n", euid);
    printf("gid  = %d\n", gid);
    printf("egid = %d\n", egid);

    if (uid == 0 || euid == 0) {
        printf("[FAIL] process is still running as root.\n");
        return 1;
    }

    printf("[OK] process is running as non-root user.\n");
    return 0;
}