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
#include "../../logger/logger.h"

#define IMAGE_SUBDIR "sandbox/image"

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

static void build_paths(const char *job_id, sandbox_paths *paths) {
    char cwd[256];
    if (getcwd(cwd, sizeof(cwd)) == NULL) {
        perror("getcwd failed");
        logger_log(LOG_ERROR, "Filesystem", "Getcwd failed. Job ID: %s", job_id);
        snprintf(cwd, sizeof(cwd), ".");
    }

    snprintf(paths->runtime_dir, PATH_SIZE, "/tmp/sandbox/job_%s", job_id);
    snprintf(paths->upper_dir, PATH_SIZE, "%s/upper", paths->runtime_dir);
    snprintf(paths->work_dir, PATH_SIZE, "%s/work", paths->runtime_dir);

    snprintf(paths->merged_dir, PATH_SIZE, "%s/merged", paths->runtime_dir);
    snprintf(paths->put_old, PATH_SIZE, "%s/.oldroot", paths->merged_dir);

    snprintf(paths->host_app_dir, PATH_SIZE, "%s/app", paths->runtime_dir);
    snprintf(paths->container_app_dir, PATH_SIZE, "%s/app", paths->merged_dir);

    // 這裡的 host_res_dir 也要改成絕對路徑，避免 Parent 找不到
    snprintf(paths->host_res_dir, PATH_SIZE, "%s/sandbox/result/job_%s", cwd, job_id);
    snprintf(paths->container_res_dir, PATH_SIZE, "%s/output", paths->merged_dir);
    
    //關鍵新增：把動態算好的絕對路徑存在 paths 結構體中（假設你的 sandbox_paths 結構體有這個欄位）
    // 或者我們可以直接在 mount_overlayfs 裡面現場動態算。
}

static int prepare_dir(const char *path, mode_t dir_mode, uid_t uid, gid_t gid, int set_owner) {
    if (mkdir_p(path, dir_mode) == -1 && errno != EEXIST) {
        fprintf(stderr, "Failed to create directory %s: ", path);
        logger_log(LOG_ERROR, "Filesystem", "Failed to create directory %s: ", path);
        perror(""); 
        return -1;
    }

    if (set_owner) {
        if (chown(path, uid, gid) == -1) {
            fprintf(stderr, "Failed to chown %s: ", path);
            logger_log(LOG_ERROR, "Filesystem", "Failed to chown %s: ", path);
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

    if (prepare_dir(paths.runtime_dir, 0777, uid, gid, 0) == -1) return -1;
    if (prepare_dir(paths.merged_dir,  0777, uid, gid, 0) == -1) return -1;

    if (prepare_dir(paths.upper_dir,   0777, uid, gid, 1) == -1) return -1;
    if (prepare_dir(paths.work_dir,    0777, uid, gid, 1) == -1) return -1;

    // 建立一個跟 app、work 平行的實體 host tmp 目錄，給予 0777 最高權限
    char host_tmp_path[512];
    snprintf(host_tmp_path, sizeof(host_tmp_path), "%s/tmp", paths.runtime_dir);
    if (prepare_dir(host_tmp_path, 0777, uid, gid, 0) == -1) return -1;
    chmod(host_tmp_path, 0777); 

    if (prepare_dir(paths.host_res_dir, 0755, uid, gid, 1) == -1) return -1;
    if (chmod(paths.host_res_dir, 0775) == -1) {
        perror("chmod host_res_dir");
        return -1;
    }

    const char *global_res_dir = "./sandbox/result";
    if (chown(global_res_dir, uid, gid) == -1) {
        perror("chown global result dir");
    }
    if (chmod(global_res_dir, 0777) == -1) {
        perror("chmod global result dir");
    }

    printf("[Parent] Runtime directories ready\n");
    logger_log(LOG_INFO, "Filesystem", "Runtime directories ready. Job ID: %s", job_id);
    return 0;
}

int mount_overlayfs(const char *job_id, const char *language){
    sandbox_paths paths;
    build_paths(job_id, &paths);

    char overlay_opts[2048];
    
    // ════════════════════════════════════════════════════════════════════
    // ★ 關鍵修復：動態取得主機 CWD 絕對路徑
    // ════════════════════════════════════════════════════════════════════
    char cwd[512];
    if (getcwd(cwd, sizeof(cwd)) == NULL) {
        snprintf(cwd, sizeof(cwd), "."); // 發生異常時的 fallback
    }

    printf("[Parent] Mounting OverlayFS for Job %s (CWD: %s)...\n", job_id, cwd);

    if (mkdir_p(paths.merged_dir, 0777) == -1 && errno != EEXIST) {
        perror("mkdir_p merged_dir failed");
        logger_log(LOG_ERROR, "Parent", "mkdir_p merged_dir failed. Job ID: %s", job_id);
        return -1;
    }
    chmod(paths.merged_dir, 0777);

    if(strcmp(language, "c") == 0){
        snprintf(
            overlay_opts,
            sizeof(overlay_opts),
            "lowerdir=%s/sandbox/image/gcc:"
            "%s/sandbox/image/base_rootfs,"
            "upperdir=%s,"
            "workdir=%s",
            cwd, cwd, paths.upper_dir, paths.work_dir
        );  
    }else if(strcmp(language, "python") == 0){
        snprintf(
            overlay_opts,
            sizeof(overlay_opts),
            "lowerdir=%s/sandbox/image/python:"
            "%s/sandbox/image/base_rootfs,"
            "upperdir=%s,"
            "workdir=%s",
            cwd, cwd, paths.upper_dir, paths.work_dir
        );
    }

    if(mount("overlay", paths.merged_dir, "overlay", 0, overlay_opts) == -1){
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

    printf("[Parent] OverlayFS mounted\n");
    logger_log(LOG_INFO, "Parent", "OverlayFS mounted. Job ID: %s", job_id);

    return 0;
}

void setup_pivot_root(const char *job_id){
    sandbox_paths paths;
    build_paths(job_id, &paths);

    printf("[Sandbox] Executing pivot_root for Job %s...\n", job_id);

    if(mount(paths.merged_dir, paths.merged_dir, NULL, MS_BIND | MS_REC, NULL) == -1){
        perror("mount bind merged");
        exit(1);
    }

    if(chdir(paths.merged_dir) == -1){
        perror("chdir merged_dir");
        exit(1);
    }

    if(mkdir(".oldroot", 0755) == -1 && errno != EEXIST){
        perror("mkdir .oldroot");
        exit(1);
    }

    if(pivot_root_syscall(".", "./.oldroot") == -1){
        perror("pivot_root");
        exit(1);
    }

    printf("[Sandbox] pivot_root success\n");
    logger_log(LOG_INFO, "Filesystem", "Pivot_root success. Job ID: %s", job_id);

    if(chdir("/") == -1){
        perror("chdir /");
        exit(1);
    }

    // 掛載 /app
    char old_app_path[512];
    snprintf(old_app_path, sizeof(old_app_path), "/.oldroot/tmp/sandbox/job_%s/app", job_id);
    mkdir("/app", 0755);
    if (mount(old_app_path, "/app", NULL, MS_BIND | MS_REC, NULL) == -1) {
        perror("[Sandbox Sec] Secure mount /app failed");
        logger_log(LOG_ERROR, "Filesystem", "Secure mount /app failed. Job ID: %s", job_id);
        exit(1);
    }
    if (mount("/app", "/app", NULL, MS_REMOUNT | MS_BIND, NULL) == -1) {
        perror("Remount /app failed");
        logger_log(LOG_ERROR, "Filesystem", "Remount /app failed. Job ID: %s", job_id);
    }

    // 掛載 /output
    char old_res_path[512];
    snprintf(old_res_path, sizeof(old_res_path), "/.oldroot/tmp/sandbox/job_%s/work", job_id);
    mkdir("/output", 0755);
    if (mount(old_res_path, "/output", NULL, MS_BIND | MS_REC, NULL) == -1) {
        perror("[Sandbox Sec] Secure mount /output failed");
        logger_log(LOG_ERROR, "Filesystem", "Secure mount /output failed. Job ID: %s", job_id);
        exit(1);
    }
    if (mount("/output", "/output", NULL, MS_REMOUNT | MS_BIND, NULL) == -1) {
        perror("Remount /output failed");
        logger_log(LOG_ERROR, "Filesystem", "Remount /output failed. Job ID: %s", job_id);
    }

    // 掛載 /proc
    if(mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) == -1){
        perror("mount proc");
        exit(1);
    }

    if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) == -1) {
        perror("Make root private failed");
    }

    // ════════════════════════════════════════════════════════════════════
    // ★ 關鍵修復點：用實體 Bind Mount 建立並掛載沙盒內部的 /tmp
    // ════════════════════════════════════════════════════════════════════
    char old_tmp_path[512];
    snprintf(old_tmp_path, sizeof(old_tmp_path), "/.oldroot/tmp/sandbox/job_%s/tmp", job_id);
    
    mkdir("/tmp", 0777);
    if (mount(old_tmp_path, "/tmp", NULL, MS_BIND | MS_REC, NULL) == -1) {
        perror("[Sandbox Sec] Secure bind mount /tmp failed");
        exit(1);
    }
    // 解開唯讀限制，讓 gcc 能夠自由讀寫
    chmod("/tmp", 0777);

    // 清理舊根目錄
    if(mount(NULL, "/.oldroot", NULL, MS_PRIVATE | MS_REC, NULL) == -1){ 
        perror("mount private oldroot"); 
        exit(1); 
    }
    if(umount2("/.oldroot", MNT_DETACH) == -1){ 
        perror("umount oldroot"); 
        exit(1); 
    }
    if(rmdir("/.oldroot") == -1){ 
        perror("rmdir oldroot failed"); 
    }

    printf("[Sandbox] Container rootfs ready for Job %s\n", job_id);
    logger_log(LOG_INFO, "Filesystem", "Container rootfs ready. Job ID: %s", job_id);
}

int cleanup_container_filesystem(const char *job_id){
    sandbox_paths paths;
    build_paths(job_id, &paths);

    char cmd[PATH_SIZE];
    printf( "[Parent] Cleaning runtime for Job %s...\n",job_id);

    if(umount2(paths.merged_dir, MNT_DETACH) == -1){
        perror("[Cleanup] umount merged");
    }

    snprintf(cmd,sizeof(cmd),"rm -rf %s",paths.runtime_dir);
    if(system(cmd) != 0){
        perror("[Cleanup] rm -rf runtime");
         logger_log(LOG_ERROR, "Filesystem", "rm -rf runtime. Job ID: %s", job_id);
    }
    else{
        printf("[Cleanup] Job %s runtime removed.\n", job_id);
        logger_log(LOG_INFO, "Filesystem", "Runtime removed. Job ID: %s", job_id);
    }

    return 0;
}