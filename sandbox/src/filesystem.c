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

#define BASE_IMAGE_DIR "./sandbox/images/base_rootfs"

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

};

int prepare_rootfs(const char *job_id){

    sandbox_paths paths;
    build_paths(job_id, &paths);

    printf(
        "[Parent] Preparing runtime for Job %s...\n",
        job_id
    );

    if(mkdir_p(paths.runtime_dir, 0755) == -1){
        perror("mkdir_p runtime_dir");
        return -1;
    }

    if(mkdir(paths.upper_dir, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir upper_dir");
        return -1;
    }

    if(mkdir(paths.work_dir, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir work_dir");
        return -1;
    }

    if(mkdir(paths.merged_dir, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir merged_dir");
        return -1;
    }

    printf("[Parent] Runtime directories ready\n");

    return 0;
}

int mount_secure_container(const char *job_id) {
    char upper_dir[512], work_dir[512], merged_dir[512]; 
    char overlay_options[2048];                          
    char target[1024];                                   
    char host_job_dir[1024], container_app_dir[1024]; // 統一在最上方宣告 1024 大小

    snprintf(upper_dir,  sizeof(upper_dir),  "./sandbox/containers/job_%s/diff", job_id);
    snprintf(work_dir,   sizeof(work_dir),   "./sandbox/containers/job_%s/work", job_id);
    snprintf(merged_dir, sizeof(merged_dir), "./sandbox/containers/job_%s/merged", job_id);

    printf("[Parent] Setting up isolated layers for Job %s...\n", job_id);

    mkdir_p(upper_dir, 0755); mkdir_p(work_dir, 0755); mkdir_p(merged_dir, 0755);

    // 掛載 OverlayFS 基礎層
    snprintf(overlay_options, sizeof(overlay_options), "lowerdir=%s,upperdir=%s,workdir=%s", BASE_IMAGE_DIR, upper_dir, work_dir);
    if (mount("overlay", merged_dir, "overlay", 0, overlay_options) == -1) {
        perror("[Parent] OverlayFS mount failed");
        return -1;
    }

    // 精準安全投影 GCC 執行檔
    printf("[Parent] Projecting minimal GCC toolchain into container...\n");
    char *binaries[] = {"gcc", "as", "ld"};
    for (int i = 0; i < 3; i++) {
        snprintf(target, sizeof(target), "%s/usr/bin/%s", merged_dir, binaries[i]);
        if (touch_file(target) != 0) return -1;
        char host_bin[64];
        snprintf(host_bin, sizeof(host_bin), "/usr/bin/%s", binaries[i]);
        if (mount(host_bin, target, NULL, MS_BIND | MS_RDONLY, NULL) == -1) {
            perror("[Parent] Mount GCC binary failed");
            return -1;
        }
    }

    // 投影系統標頭檔與類庫
    snprintf(target, sizeof(target), "%s/usr/include", merged_dir);
    if (mount("/usr/include", target, NULL, MS_BIND | MS_RDONLY, NULL) == -1) return -1;

    char *lib_dirs[] = {"/lib", "/lib64", "/usr/lib"};
    for (int i = 0; i < 3; i++) {
        snprintf(target, sizeof(target), "%s%s", merged_dir, lib_dirs[i]);
        if (mount(lib_dirs[i], target, NULL, MS_BIND | MS_RDONLY, NULL) == -1) return -1;
    }

    // 資料注入 Volume Mount (已修復重複宣告與截斷問題)
    snprintf(host_job_dir, sizeof(host_job_dir), "./sandbox/tmp/job_%s", job_id);
    snprintf(container_app_dir, sizeof(container_app_dir), "%s/app", merged_dir);
    mkdir_p(host_job_dir, 0755);

    if (mount(host_job_dir, container_app_dir, NULL, MS_BIND, NULL) == -1) {
        perror("[Parent] Volume mount bind failed");
        return -1;
    }

    printf("[Parent] Container filesystem stack for Job %s is perfectly ready!\n", job_id);
    return 0;
}

int mount_overlayfs(const char *job_id){

    sandbox_paths paths;

    build_paths(job_id, &paths);

    char overlay_opts[2048];

    printf(
        "[Parent] Mounting OverlayFS for Job %s...\n",
        job_id
    );

    snprintf(
        overlay_opts,
        sizeof(overlay_opts),
        "lowerdir=./sandbox/image/gcc,"
        "upperdir=%s,"
        "workdir=%s",
        paths.upper_dir,
        paths.work_dir
    );

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

    if(mount(
        paths.host_app_dir,
        paths.container_app_dir,
        NULL,
        MS_BIND,
        NULL
    ) == -1){
        perror("mount app bind");
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

    if(mkdir(paths.put_old, 0755) == -1 &&
       errno != EEXIST){
        perror("mkdir oldroot");
        exit(1);
    }

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

    if(pivot_root_syscall(
        paths.merged_dir,
        paths.put_old
    ) == -1){
        perror("pivot_root");
        exit(1);
    }

    printf("[Sandbox] pivot_root success\n");

    if(chdir("/") == -1){
        perror("chdir");
        exit(1);
    }

    if(mount("proc","/proc","proc", 0,NULL) == -1){
        perror("mount proc");
        exit(1);
    }

    if(mount(NULL,"/.oldroot",NULL,MS_PRIVATE | MS_REC,NULL) == -1){
        perror("mount private oldroot");
        exit(1);
    }

    if(umount2( "/.oldroot",MNT_DETACH) == -1){
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