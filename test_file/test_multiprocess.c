#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <time.h>

#define WORKERS 2
#define LOOP_COUNT 900000000ULL

void cpu_work(int id) {
    volatile unsigned long long x = 0;

    for (unsigned long long i = 0; i < LOOP_COUNT; i++) {
        x += i % 97;
    }

    printf("worker %d done, x=%llu\n", id, x);
    fflush(stdout);
}

int main() {
    time_t start = time(NULL);

    for (int i = 0; i < WORKERS; i++) {
        pid_t pid = fork();

        if (pid < 0) {
            perror("fork");
            return 1;
        }

        if (pid == 0) {
            cpu_work(i);
            return 0;
        }
    }

    for (int i = 0; i < WORKERS; i++) {
        wait(NULL);
    }

    time_t end = time(NULL);

    printf("all workers done\n");
    printf("wall time: %ld sec\n", end - start);
    fflush(stdout);

    return 0;
}