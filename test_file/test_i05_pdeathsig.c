#include <stdio.h>
#include <sys/prctl.h>
#include <signal.h>
#include <errno.h>
#include <string.h>

int main() {
    int sig = 0;

    printf("PDEATHSIG check\n");

    if (prctl(PR_GET_PDEATHSIG, &sig) == -1) {
        printf("[FAIL] PR_GET_PDEATHSIG failed: %s\n", strerror(errno));
        return 1;
    }

    printf("Current PDEATHSIG = %d\n", sig);

    if (sig == SIGKILL) {
        printf("[OK] PR_SET_PDEATHSIG is SIGKILL.\n");
        return 0;
    }

    if (sig == 0) {
        printf("[WARN] PDEATHSIG is not set in this process.\n");
        printf("This may be set in sandbox init process, not user payload.\n");
        return 0;
    }

    printf("[WARN] PDEATHSIG is set, but not SIGKILL.\n");
    return 0;
}