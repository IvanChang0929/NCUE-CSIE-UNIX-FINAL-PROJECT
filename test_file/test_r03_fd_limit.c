#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

int main() {
    int fds[1024];
    int count = 0;

    printf("FD limit test start...\n");

    while (count < 1024) {
        int fd = open("/proc/self/status", O_RDONLY);

        /*if (fd == -1) {
            printf("open failed at fd count %d\n", count);
            printf("errno = %d (%s)\n", errno, strerror(errno));

            if (errno == EMFILE) {
                printf("[OK] fd limit works: Too many open files.\n");
                return 0;
            }

            printf("[WARN] open failed, but not because of fd limit.\n");
            return 1;
        }*/

        fds[count] = fd;
        printf("opened fd %d\n", fd);
        count++;
    }

    printf("[FAIL] opened too many files without hitting fd limit.\n");

    for (int i = 0; i < count; i++) {
        close(fds[i]);
    }

    return 1;
}