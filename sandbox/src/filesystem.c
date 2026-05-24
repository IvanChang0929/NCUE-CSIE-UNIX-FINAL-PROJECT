#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/mount.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <errno.h>

#include "filesystem.h"

#define BASE_IMAGE_DIR "./sandbox/image/base_rootfs"

uid_t get_real_uid(void) {
    char *sudo_uid = getenv("SUDO_UID");
    return sudo_uid ? atoi(sudo_uid) : getuid();
}

gid_t get_real_gid(void) {
    char *sudo_gid = getenv("SUDO_GID");
    return sudo_gid ? atoi(sudo_gid) : getgid();
}

static int touch_file(const char *path) {
    FILE *f = fopen(path, "w");
    if (f == NULL) return -1;
    fclose(f);
    return 0;
}

static int mkdir_p(const char *path, mode_t mode) {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    size_t len = strlen(tmp);
    if (tmp[len - 1] == '/') tmp[len - 1] = 0;
    
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            if (mkdir(tmp, mode) == -1 && errno != EEXIST) return -1;
            *p = '/';
        }
    }
    if (mkdir(tmp, mode) == -1 && errno != EEXIST) return -1;
    return 0;
}

static int pivot_root_syscall(const char *new_root, const char *put_old){
    return syscall(SYS_pivot_root, new_root, put_old);
}

static void build_paths(const char *job_id,sandbox_paths *paths){

    snprintf(paths->runtime_dir,PATH_SIZE,"/tmp/sandbox/job_%s",job_id);
    snprintf(paths->upper_dir,PATH_SIZE,"%s/upper",paths->runtime_dir);
    snprintf(paths->work_dir, PATH_SIZE,"%s/work",paths->runtime_dir);

    snprintf(paths->merged_dir,PATH_SIZE,"%s/merged",paths->runtime_dir);
    snprintf(paths->put_old,PATH_SIZE,"%s/.oldroot",paths->merged_dir);

    snprintf(paths->host_app_dir,PATH_SIZE,"%s/app", paths->runtime_dir);
    snprintf(paths->container_app_dir,PATH_SIZE, "%s/app",paths->merged_dir);

    snprintf(paths->host_res_dir,PATH_SIZE, "./sandbox/result/job_%s", job_id);
    snprintf(paths->container_res_dir,PATH_SIZE, "%s/output",paths->merged_dir);

};

static int prepare_dir(const char *path, mode_t dir_mode, uid_t uid, gid_t gid, int set_owner) {
    if (mkdir_p(path, dir_mode) == -1 && errno != EEXIST) {
        fprintf(stderr, "Failed to create directory %s: ", path);
        perror(""); 
        return -1;
    }

    if (set_owner) {
        if (chown(path, uid, gid) == -1) {
            fprintf(stderr, "Failed to chown %s: ", path);
            perror("");
            return -1;
        }
    }
    return 0;
}

int prepare_rootfs(const char *job_id) {
    sandbox_paths paths = {0}; 
    build_paths(job_id, &paths);

    printf("[Parent] Preparing runtime for Job %s...\n", job_id);

    uid_t uid = get_real_uid();
    gid_t gid = get_real_gid();

    if (prepare_dir(paths.runtime_dir, 0755, uid, gid, 0) == -1) return -1;
    if (prepare_dir(paths.merged_dir,  0755, uid, gid, 0) == -1) return -1;

    if (prepare_dir(paths.upper_dir,   0755, uid, gid, 1) == -1) return -1;
    if (prepare_dir(paths.work_dir,    0755, uid, gid, 1) == -1) return -1;

    if (prepare_dir(paths.host_res_dir, 0755, uid, gid, 1) == -1) return -1;
    if (chmod(paths.host_res_dir, 0775) == -1) {
        perror("chmod host_res_dir");
        return -1;
    }

    const char *global_res_dir = "./sandbox/result";
    if (chown(global_res_dir, uid, gid) == -1) {
        perror("chown global result dir");
    }
    if (chmod(global_res_dir, 0775) == -1) {
        perror("chmod global result dir");
    }

    printf("[Parent] Runtime directories ready\n");
    return 0;
}

int mount_overlayfs(const char *job_id,const char *language){

    sandbox_paths paths;

    build_paths(job_id, &paths);

    char overlay_opts[2048];

    printf(
        "[Parent] Mounting OverlayFS for Job %s...\n",
        job_id
    );

    if(strcmp(language, "c") == 0){
        snprintf(
            overlay_opts,
            sizeof(overlay_opts),
            "lowerdir=./sandbox/image/gcc:"
            "./sandbox/image/base_rootfs,"
            "upperdir=%s,"
            "workdir=%s",
            paths.upper_dir,
            paths.work_dir
        );  
    }else if(strcmp(language, "python") == 0){
        snprintf(
            overlay_opts,
            sizeof(overlay_opts),
            "lowerdir=./sandbox/image/python:"
            "./sandbox/image/base_rootfs,"
            "upperdir=%s,"
            "workdir=%s",
            paths.upper_dir,
            paths.work_dir
        );
    }

    if(mount(
        "overlay",
        paths.merged_dir,
        "overlay",
        0,
        overlay_opts
    ) == -1){
        perror("mount overlay");
        return -1;
    }

    if(mkdir_p(paths.container_app_dir, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir container_app_dir");
        return -1;
    }

    if(mkdir_p(paths.container_res_dir, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir container_res_dir");
        return -1;
    }

    if(mount(
        paths.host_app_dir,
        paths.container_app_dir,
        NULL,
        MS_BIND | MS_REC,
        NULL
    ) == -1){
        perror("mount app bind");
        return -1;
    }

    if(mount(
        paths.host_res_dir,
        paths.container_res_dir,
        NULL,
        MS_BIND | MS_REC,
        NULL
    ) == -1){
        perror("mount result bind");
        return -1;
    }

    printf("[Parent] OverlayFS mounted\n");

    return 0;
}

void setup_pivot_root(const char *job_id){

    sandbox_paths paths;
    build_paths(job_id, &paths);

    printf(
        "[Sandbox] Executing pivot_root for Job %s...\n",
        job_id
    );

    if(mount(
        paths.merged_dir,
        paths.merged_dir,
        NULL,
        MS_BIND | MS_REC,
        NULL
    ) == -1){
        perror("mount bind merged");
        exit(1);
    }

    if(chdir(paths.merged_dir) == -1){
        perror("chdir merged_dir");
        exit(1);
    }

    // ★ 在 child namespace 建立
    if(mkdir(".oldroot", 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir .oldroot");
        exit(1);
    }

    if(pivot_root_syscall(".", "./.oldroot") == -1){
        perror("pivot_root");
        exit(1);
    }

    printf("[Sandbox] pivot_root success\n");

    if(chdir("/") == -1){
        perror("chdir /");
        exit(1);
    }

    if(mount("proc", "/proc", "proc", 0, NULL) == -1){
        perror("mount proc");
        exit(1);
    }

    if(mount(NULL, "/.oldroot", NULL,
        MS_PRIVATE | MS_REC, NULL) == -1){
        perror("mount private oldroot");
        exit(1);
    }

    if(umount2("/.oldroot", MNT_DETACH) == -1){
        perror("umount oldroot");
        exit(1);
    }

    if(rmdir("/.oldroot") == -1){
        perror("rmdir oldroot");
        exit(1);
    }

    printf(
        "[Sandbox] Container rootfs ready for Job %s\n",
        job_id
    );
}

int cleanup_container_filesystem(const char *job_id){

    sandbox_paths paths;
    build_paths(job_id, &paths);

    char cmd[PATH_SIZE];

    printf( "[Parent] Cleaning runtime for Job %s...\n",job_id);

    if(umount2(paths.merged_dir,MNT_DETACH) == -1){
        perror("[Cleanup] umount merged");
    }

    snprintf(cmd,sizeof(cmd),"rm -rf %s",paths.runtime_dir);

    if(system(cmd) != 0){
        perror("[Cleanup] rm -rf runtime");
    }
    else{
        printf(
            "[Cleanup] Job %s runtime removed.\n",
            job_id
        );
    }

    return 0;
}