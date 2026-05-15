#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <sys/mount.h>

#include "namespace.h"

//之後需要 network namespace 在寫 (目前預設不需要網路)

void setup_mount_namespace(){
    if(mount(NULL,"/",NULL,MS_REC | MS_PRIVATE,NULL) == -1){
        perror("mount MS_PRIVATE");
        exit(1);
    }
    printf("[Sandbox] Mount propagation isolated\n");

    if(mount("proc","/proc","proc",0,NULL) == -1){
        perror("mount proc");
        exit(1);
    }
    printf("[Sandbox] /proc remounted\n");
}

static void write_file(const char *path, const char *data) {
    FILE *f = fopen(path, "w");
    if (f == NULL) {
        perror("fopen in write_file");
        exit(1);
    }
    if (fprintf(f, "%s", data) < 0) {
        perror("fprintf in write_file");
        fclose(f);
        exit(1);
    }
    fclose(f);
}

void setup_uid_gid_map(pid_t pid){ //需要採用 docker 的預設？

    char path[256];
    char map[256];

    //setgroups
    snprintf(path,sizeof(path),"/proc/%d/setgroups",pid);
    write_file(path, "deny");

    //uid_map
    snprintf(path,sizeof(path),"/proc/%d/uid_map",pid);
    snprintf(map, sizeof(map),"0 %d 1\n",getuid());
    write_file(path, map);

    //gid_map
    snprintf(path,sizeof(path),"/proc/%d/gid_map",pid);
    snprintf(map,sizeof(map),"0 %d 1\n",getgid());
    write_file(path, map);

    printf("[Sandbox] UID/GID mapping configured\n");
}