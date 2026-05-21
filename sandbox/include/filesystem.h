#ifndef FILESYSTEM_H
#define FILESYSTEM_H

#define PATH_SIZE 1024

typedef struct sandbox_paths {
    char runtime_dir[PATH_SIZE];
    char upper_dir[PATH_SIZE];
    char work_dir[PATH_SIZE];

    char merged_dir[PATH_SIZE];
    char put_old[PATH_SIZE];

    char host_app_dir[PATH_SIZE];
    char container_app_dir[PATH_SIZE];

} sandbox_paths;

int prepare_rootfs(const char *job_id);
int mount_secure_container(const char *job_id);
int mount_overlayfs(const char *job_id);
void setup_pivot_root(const char *job_id);
int cleanup_container_filesystem(const char *job_id);

#endif 