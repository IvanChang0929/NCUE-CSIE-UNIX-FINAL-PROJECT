#include <stdio.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/ptrace.h>
#include <errno.h>
#include <string.h>

int main() {
    long ret;

    printf("Seccomp violation test\n");
    printf("Trying blocked syscall: ptrace\n");
    fflush(stdout);

    ret = syscall(SYS_ptrace, PTRACE_TRACEME, 0, NULL, NULL);

    printf("ptrace returned: %ld\n", ret);

    if (ret == -1) {
        printf("errno = %d (%s)\n", errno, strerror(errno));
        printf("[OK] ptrace syscall was denied.\n");
        return 0;
    }

    printf("[FAIL] ptrace syscall succeeded. Seccomp policy may be too loose.\n");
    return 1;
}