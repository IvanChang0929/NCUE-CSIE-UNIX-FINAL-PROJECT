#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BLOCK_SIZE (10 * 1024 * 1024)

int main() {
    void *blocks[10000];
    int count = 0;

    printf("Memory limit test start...\n");
    fflush(stdout);

    while (1) {
        blocks[count] = malloc(BLOCK_SIZE);

        if (blocks[count] == NULL) {
            printf("malloc failed after about %d MB\n", count * 10);
            fflush(stdout);
            return 1;
        }

        memset(blocks[count], 1, BLOCK_SIZE);

        count++;
        printf("allocated about %d MB\n", count * 10);
        fflush(stdout);

        usleep(100000);
    }

    return 0;
}