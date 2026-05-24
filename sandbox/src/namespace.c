#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <sys/mount.h>

#include "namespace.h"
#include "logger.h"

//之後需要網路在寫 (目前預設不需要網路)

void setup_mount_namespace(){
    if(mount(NULL,"/",NULL,MS_REC | MS_PRIVATE,NULL) == -1){
        perror("mount MS_PRIVATE");
        exit(1);
    }
    printf("[Sandbox] Mount propagation isolated\n");
    logger_log(LOG_INFO, "Sandbox", "Mount propagation isolated.");
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

void setup_uid_gid_map(pid_t pid){

    char path[256];
    char map[256];

    uid_t host_uid;
    gid_t host_gid;

    char *sudo_uid = getenv("SUDO_UID");
    char *sudo_gid = getenv("SUDO_GID");

    if(sudo_uid && sudo_gid){
        host_uid = atoi(sudo_uid);
        host_gid = atoi(sudo_gid);
    }
    else{
        host_uid = getuid();
        host_gid = getgid();
    }

    snprintf(path,sizeof(path),"/proc/%d/setgroups",pid);
    write_file(path, "deny");

    snprintf(path,sizeof(path),"/proc/%d/uid_map",pid);
    snprintf(map,sizeof(map),"0 %d 1\n",host_uid);
    write_file(path, map);

    snprintf(path,sizeof(path),"/proc/%d/gid_map",pid);
    snprintf(map,sizeof(map), "0 %d 1\n",host_gid);
    write_file(path, map);

    printf(
        "[Parent] UID/GID mapping configured "
        "(container root -> host %d:%d)\n",
        host_uid,
        host_gid
    );
    logger_log(LOG_INFO, "Parent", "UID/GID mapping configured (container root -> host %d:%d)", host_uid, host_gid);
}