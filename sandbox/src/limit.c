#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>

#include <sys/resource.h>

#include "limit.h"

#define MEMORY_LIMIT (128 * 1024 * 1024)
#define CPU_LIMIT 2

void setup_resource_limits(){

    struct rlimit cpu_limit;

    cpu_limit.rlim_cur = CPU_LIMIT;
    cpu_limit.rlim_max = CPU_LIMIT;

    if(setrlimit(RLIMIT_CPU,&cpu_limit) == -1){
        perror("setrlimit CPU");
        exit(1);
    }

    struct rlimit mem_limit;

    mem_limit.rlim_cur = MEMORY_LIMIT;
    mem_limit.rlim_max = MEMORY_LIMIT;

    if(setrlimit(RLIMIT_AS,&mem_limit) == -1){
        perror("setrlimit MEM");
        exit(1);
    }

    printf("[Sandbox] Resource limits applied\n");
}