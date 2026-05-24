#include <stdio.h>
#include <time.h>

int main() {
    volatile unsigned long long x = 0;

    for (int sec = 0; sec < 6; sec++) {
        time_t start = time(NULL);

        while (time(NULL) - start < 1) {
            for (int i = 0; i < 1000000; i++) {
                x += i;
            }
        }

        printf("cpu busy %d sec, x=%llu\n", sec + 1, x);
        fflush(stdout);
    }

    return 0;
}