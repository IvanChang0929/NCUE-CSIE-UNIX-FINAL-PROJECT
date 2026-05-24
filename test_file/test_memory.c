#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BLOCK_SIZE (10 * 1024 * 1024)  // 每次吃 10 MB

int main() {
    void *blocks[10000];
    int count = 0;

    printf("Start memory explosion test...\n");
    fflush(stdout);

    while (1) {
        blocks[count] = malloc(BLOCK_SIZE);

        // 一定要 memset，否則 Linux 可能只是保留虛擬記憶體，實體記憶體不一定馬上上升
        memset(blocks[count], 1, BLOCK_SIZE);

        count++;

        printf("allocated about %d MB\n", count * 10);
        fflush(stdout);

        usleep(100000); // 0.1 秒，讓前端看得到 Memory 慢慢上升
    }

    sleep(2);
    return 0;
}