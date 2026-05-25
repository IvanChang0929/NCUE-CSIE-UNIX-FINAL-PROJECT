#include <stdio.h>

int main() {
    volatile unsigned long long x = 0;

    printf("CPU limit test start...\n");
    fflush(stdout);

    while (1) {
        for (int i = 0; i < 1000000; i++) {
            x += i;
        }
    }

    return 0;
}